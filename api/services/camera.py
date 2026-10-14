"""
services/camera.py

Caméras IP (optionnel) via go2rtc. La plupart des caméras (Reolink, Tapo...)
diffusent en RTSP, qu'un navigateur ne sait pas lire : go2rtc s'y connecte une
seule fois (les Tapo limitent le nombre de flux simultanés) et le remet au
navigateur en fMP4 (MSE) sur un websocket, ou en image JPEG.

go2rtc n'est jamais exposé : l'API relaie ses réponses après contrôle des
droits, et les adresses RTSP (avec identifiants) ne quittent pas le serveur.
Son API n'ayant pas d'authentification (et acceptant des sources « exec: »),
les sources sont construites ici, à partir de champs validés.
"""

import asyncio
import base64
import hashlib
import logging
import re
import time
import uuid
from urllib.parse import quote

import httpx
from cryptography.fernet import Fernet, InvalidToken

from models.camera import Camera
from settings import settings

logger = logging.getLogger(__name__)

# Chemins des flux par marque (principal, secondaire)
PRESETS: dict[str, tuple[str, str]] = {
    "reolink": ("h264Preview_01_main", "h264Preview_01_sub"),
    "tapo": ("stream1", "stream2"),
    "rtsp": ("", ""),
}
QUALITIES = ("main", "sub")

HOST_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$")
# Pas d'espace ni de « # » (paramètres de source go2rtc) dans les chemins
PATH_RE = re.compile(r"^[A-Za-z0-9._~/?=&%:+-]{0,255}$")

FRAME_TIMEOUT = 20.0
SNAPSHOT_CACHE_SECONDS = 5
_snapshots: dict[tuple[int, str], tuple[float, bytes]] = {}


class CameraError(Exception):
    """Erreur lisible par l'utilisateur ; status : code HTTP à renvoyer."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def enabled() -> bool:
    return bool(settings.go2rtc_url.strip())


def _base_url() -> str:
    if not enabled():
        raise CameraError("Caméras désactivées : le service vidéo go2rtc n'est pas configuré.", 503)
    return settings.go2rtc_url.strip().rstrip("/")


def ws_base_url() -> str:
    base = _base_url()
    return "ws" + base[4:] if base.startswith("http") else base


# --- Mot de passe chiffré ---------------------------------------------------------


def _fernet() -> Fernet:
    digest = hashlib.sha256(f"aquas-camera:{settings.secret_key}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_password(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_password(value: str | None) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        logger.warning("Mot de passe de caméra illisible (clé secrète changée ?)")
        return ""


# --- Sources RTSP -------------------------------------------------------------------


def validate_fields(host: str, port: int, main_path: str, sub_path: str) -> None:
    if not HOST_RE.match(host or ""):
        raise CameraError("Adresse de la caméra invalide (IP ou nom d'hôte, sans « rtsp:// »).", 400)
    if not 1 <= int(port) <= 65535:
        raise CameraError("Port invalide.", 400)
    for path in (main_path, sub_path):
        if not PATH_RE.match(path or ""):
            raise CameraError("Chemin de flux invalide (pas d'espace ni de « # »).", 400)
    if not (main_path or sub_path):
        raise CameraError("Indique au moins le chemin du flux principal.", 400)


def rtsp_url(host: str, port: int, username: str, password: str, path: str) -> str:
    auth = ""
    if username:
        auth = quote(username, safe="") + (":" + quote(password, safe="") if password else "") + "@"
    return f"rtsp://{auth}{host}:{int(port)}/{path.lstrip('/')}"


def camera_path(camera: Camera, quality: str) -> str:
    if quality == "sub":
        return camera.sub_path or camera.main_path
    return camera.main_path or camera.sub_path


def camera_source(camera: Camera, quality: str) -> str:
    return rtsp_url(camera.host, camera.port, camera.username, decrypt_password(camera.password_encrypted),
                    camera_path(camera, quality))


def stream_name(camera_id: int, quality: str) -> str:
    return f"aquas_cam_{camera_id}_{quality}"


# --- go2rtc -------------------------------------------------------------------------


UNREACHABLE = "Caméra injoignable : vérifie l'adresse, le port et que le RTSP est activé sur la caméra."
NO_IMAGE = "La caméra répond mais n'envoie pas d'image : vérifie l'identifiant, le mot de passe et le chemin du flux."


async def _reachable(host: str, port: int) -> bool:
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, int(port)), timeout=3)
    except (OSError, asyncio.TimeoutError):
        return False
    writer.close()
    return True


async def _no_image(host: str, port: int) -> "CameraError":
    # go2rtc répond 200 sans image en cas d'échec (motif dans ses journaux
    # seulement) : une connexion TCP distingue « injoignable » de « refusé »
    return CameraError(NO_IMAGE if await _reachable(host, port) else UNREACHABLE)


async def _register(client: httpx.AsyncClient, name: str, source: str) -> None:
    # PATCH : crée ou met à jour le flux en mémoire (sans fichier de config)
    response = await client.patch(f"{_base_url()}/api/streams", params={"name": name, "src": source})
    if response.status_code >= 400:
        logger.warning("go2rtc refuse le flux %s : %s", name, response.text.strip()[:200])
        raise CameraError("Source vidéo refusée par go2rtc.", 400)


async def ensure_stream(camera: Camera, quality: str) -> str:
    name = stream_name(camera.id, quality)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await _register(client, name, camera_source(camera, quality))
    except httpx.HTTPError as exc:
        logger.warning("go2rtc injoignable (%s) : %s", settings.go2rtc_url, exc)
        raise CameraError("Service vidéo go2rtc injoignable.", 503) from exc
    return name


async def _frame(client: httpx.AsyncClient, name: str, host: str, port: int) -> bytes:
    response = await client.get(f"{_base_url()}/api/frame.jpeg", params={"src": name})
    if response.status_code >= 400 or not response.content.startswith(b"\xff\xd8"):
        logger.info("Image indisponible pour %s (HTTP %s)", name, response.status_code)
        raise await _no_image(host, port)
    return response.content


async def snapshot(camera: Camera, quality: str = "sub", fresh: bool = False) -> bytes:
    key = (camera.id, quality)
    cached = _snapshots.get(key)
    if cached and not fresh and time.monotonic() - cached[0] < SNAPSHOT_CACHE_SECONDS:
        return cached[1]
    name = await ensure_stream(camera, quality)
    try:
        async with httpx.AsyncClient(timeout=FRAME_TIMEOUT) as client:
            image = await _frame(client, name, camera.host, camera.port)
    except httpx.TimeoutException as exc:
        raise CameraError("La caméra ne répond pas (délai dépassé).", 504) from exc
    except httpx.HTTPError as exc:
        raise CameraError("Service vidéo go2rtc injoignable.", 503) from exc
    _snapshots[key] = (time.monotonic(), image)
    return image


def forget(camera_id: int) -> None:
    for quality in QUALITIES:
        _snapshots.pop((camera_id, quality), None)


async def remove_streams(camera_id: int) -> None:
    forget(camera_id)
    if not enabled():
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            for quality in QUALITIES:
                await client.delete(f"{_base_url()}/api/streams", params={"src": stream_name(camera_id, quality)})
    except httpx.HTTPError:
        pass  # go2rtc redémarré ou arrêté : rien à nettoyer


async def test_source(host: str, port: int, username: str, password: str, path: str) -> int:
    """Tente une image avec ces réglages (avant enregistrement) ; renvoie sa taille."""
    name = f"aquas_test_{uuid.uuid4().hex[:12]}"
    try:
        async with httpx.AsyncClient(timeout=FRAME_TIMEOUT) as client:
            await _register(client, name, rtsp_url(host, port, username, password, path))
            try:
                return len(await _frame(client, name, host, port))
            finally:
                await client.delete(f"{_base_url()}/api/streams", params={"src": name})
    except httpx.TimeoutException as exc:
        raise CameraError("La caméra ne répond pas (délai dépassé).", 504) from exc
    except httpx.HTTPError as exc:
        raise CameraError("Service vidéo go2rtc injoignable.", 503) from exc
