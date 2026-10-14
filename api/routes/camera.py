"""
camera.py (routes)

Caméras IP d'un aquarium (optionnel, voir services/camera.py) : configuration,
image, capture vers les photos de l'aquarium et direct (websocket relayé).
Réservé aux comptes qui voient les aquariums, sauf le compte « bourse ».
"""

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path

import aiohttp
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from middleware.auth import FRAG_ROLES, ROLE, min_role_required, verify_access_token
from middleware.database import SessionLocal, get_db
from models.aquarium import Aquarium
from models.camera import Camera
from models.photo import Photo, PhotoType
from routes.photo import UPLOAD_ROOT
from schemas.camera import (
    CameraCreate,
    CameraRead,
    CameraStatus,
    CameraTest,
    CameraUpdate,
    Quality,
)
from schemas.photo import PhotoRead
from services import camera as svc

logger = logging.getLogger(__name__)

WS_UNAUTHORIZED = 4401
WS_FORBIDDEN = 4403
WS_UNAVAILABLE = 4503
# Un onglet oublié ne garde pas la caméra occupée indéfiniment (le lecteur se reconnecte)
LIVE_MAX_SECONDS = 30 * 60


def _can_view(role: str | None) -> bool:
    # Le compte « bourse » ne voit que les boutures : pas l'intérieur de la maison
    return ROLE.get(role or "", 0) >= ROLE["consult"] and role not in FRAG_ROLES


def camera_viewer(identity: dict = Depends(min_role_required("consult"))) -> dict:
    if not _can_view(identity.get("role")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Caméras non accessibles avec ce compte.")
    return identity


router = APIRouter(prefix="/cameras", tags=["cameras"], dependencies=[Depends(camera_viewer)])
live_router = APIRouter(prefix="/cameras", tags=["cameras"])
EXTRA_ROUTERS = (live_router,)


def _raise(exc: svc.CameraError):
    raise HTTPException(status_code=exc.status, detail=str(exc))


def _read(camera: Camera) -> CameraRead:
    return CameraRead.model_validate(
        {**{c.name: getattr(camera, c.name) for c in Camera.__table__.columns}, "has_password": bool(camera.password_encrypted)}
    )


def _get(db: Session, camera_id: int) -> Camera:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Caméra introuvable.")
    return camera


def _ensure_unique_name(db: Session, name: str, aquarium_id: int, camera_id: int | None = None) -> None:
    query = db.query(Camera).filter(func.lower(Camera.name) == name.strip().lower(), Camera.aquarium_id == aquarium_id)
    if camera_id is not None:
        query = query.filter(Camera.id != camera_id)
    if query.first():
        raise HTTPException(status_code=400, detail=f"Une caméra porte déjà le nom « {name.strip()} » dans cet aquarium.")


def _apply(camera: Camera, data: CameraCreate | CameraUpdate) -> None:
    try:
        svc.validate_fields(data.host.strip(), data.port, data.main_path.strip(), data.sub_path.strip())
    except svc.CameraError as exc:
        _raise(exc)
    camera.name = data.name.strip()
    camera.brand = data.brand
    camera.host = data.host.strip()
    camera.port = data.port
    camera.username = data.username.strip()
    camera.main_path = data.main_path.strip().lstrip("/")
    camera.sub_path = data.sub_path.strip().lstrip("/")
    camera.sort_order = data.sort_order
    if data.password:
        camera.password_encrypted = svc.encrypt_password(data.password)
    elif isinstance(data, CameraUpdate) and data.clear_password:
        camera.password_encrypted = None


@router.get("/status", response_model=CameraStatus)
def camera_status():
    return CameraStatus(
        enabled=svc.enabled(),
        presets={brand: {"main": main, "sub": sub} for brand, (main, sub) in svc.PRESETS.items()},
    )


@router.get("/", response_model=list[CameraRead])
def list_cameras(aquarium_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Camera)
    if aquarium_id is not None:
        query = query.filter(Camera.aquarium_id == aquarium_id)
    return [_read(c) for c in query.order_by(Camera.aquarium_id, Camera.sort_order, Camera.id).all()]


@router.post("/", response_model=CameraRead, status_code=201, dependencies=[Depends(min_role_required("manager"))])
def create_camera(data: CameraCreate, db: Session = Depends(get_db)):
    if not db.get(Aquarium, data.aquarium_id):
        raise HTTPException(status_code=404, detail="Aquarium introuvable.")
    _ensure_unique_name(db, data.name, data.aquarium_id)
    camera = Camera(aquarium_id=data.aquarium_id)
    _apply(camera, data)
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return _read(camera)


@router.put("/{camera_id}", response_model=CameraRead, dependencies=[Depends(min_role_required("manager"))])
async def update_camera(camera_id: int, data: CameraUpdate, db: Session = Depends(get_db)):
    camera = _get(db, camera_id)
    _ensure_unique_name(db, data.name, camera.aquarium_id, camera_id)
    _apply(camera, data)
    db.commit()
    db.refresh(camera)
    svc.forget(camera_id)
    return _read(camera)


@router.delete("/{camera_id}", status_code=204, dependencies=[Depends(min_role_required("manager"))])
async def delete_camera(camera_id: int, db: Session = Depends(get_db)):
    camera = _get(db, camera_id)
    db.delete(camera)
    db.commit()
    await svc.remove_streams(camera_id)
    return Response(status_code=204)


@router.post("/test", dependencies=[Depends(min_role_required("manager"))])
async def test_camera(data: CameraTest, db: Session = Depends(get_db)):
    password = data.password
    if not password and data.camera_id is not None:
        password = svc.decrypt_password(_get(db, data.camera_id).password_encrypted)
    try:
        svc.validate_fields(data.host.strip(), data.port, data.path.strip(), "")
        size = await svc.test_source(data.host.strip(), data.port, data.username.strip(), password, data.path.strip())
    except svc.CameraError as exc:
        _raise(exc)
    return {"ok": True, "message": f"Image reçue ({size // 1024} Ko)."}


@router.get("/{camera_id}/snapshot")
async def camera_snapshot(camera_id: int, quality: Quality = "sub", db: Session = Depends(get_db)):
    camera = _get(db, camera_id)
    try:
        image = await svc.snapshot(camera, quality)
    except svc.CameraError as exc:
        _raise(exc)
    return Response(content=image, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/{camera_id}/capture", response_model=PhotoRead, status_code=201,
             dependencies=[Depends(min_role_required("user"))])
async def capture_photo(camera_id: int, db: Session = Depends(get_db)):
    """Image du flux principal ajoutée aux photos de l'aquarium."""
    camera = _get(db, camera_id)
    try:
        image = await svc.snapshot(camera, "main", fresh=True)
    except svc.CameraError as exc:
        _raise(exc)
    folder = os.path.join(UPLOAD_ROOT, PhotoType.aquariums.value, str(camera.aquarium_id))
    os.makedirs(folder, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    await asyncio.to_thread(Path(folder, filename).write_bytes, image)
    has_main = (
        db.query(Photo)
        .filter(Photo.entity_type == PhotoType.aquariums, Photo.entity_id == camera.aquarium_id, Photo.is_main.is_(True))
        .first()
    )
    photo = Photo(filename=filename, entity_type=PhotoType.aquariums, entity_id=camera.aquarium_id, is_main=not has_main)
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


@live_router.websocket("/{camera_id}/live")
async def camera_live(websocket: WebSocket, camera_id: int, quality: Quality = "sub"):
    """
    Direct relayé depuis go2rtc (protocole MSE de go2rtc : le navigateur envoie
    {"type": "mse", "value": codecs}, reçoit le type puis les segments fMP4).
    Premier message : {"type": "auth", "token": "<jeton>"} (jamais dans l'URL).
    """
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        payload = verify_access_token(str(json.loads(first).get("token") or ""))
    except (asyncio.TimeoutError, ValueError, AttributeError, HTTPException, WebSocketDisconnect):
        await _close(websocket, WS_UNAUTHORIZED)
        return
    if not _can_view(payload.get("role")):
        await _close(websocket, WS_FORBIDDEN)
        return

    with SessionLocal() as db:
        camera = db.get(Camera, camera_id)
        if camera:
            db.expunge(camera)
    if not camera:
        await _close(websocket, WS_FORBIDDEN)
        return
    try:
        name = await svc.ensure_stream(camera, quality)
        upstream_url = f"{svc.ws_base_url()}/api/ws?src={name}"
    except svc.CameraError:
        await _close(websocket, WS_UNAVAILABLE)
        return

    try:
        async with aiohttp.ClientSession() as session, session.ws_connect(
            upstream_url, heartbeat=30, max_msg_size=0
        ) as upstream:
            await _relay(websocket, upstream)
    except aiohttp.ClientError as exc:
        logger.warning("Direct caméra %s impossible : %s", camera_id, exc)
        await _close(websocket, WS_UNAVAILABLE)


async def _relay(websocket: WebSocket, upstream: aiohttp.ClientWebSocketResponse) -> None:
    async def to_upstream():
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            if message.get("text") is not None:
                await upstream.send_str(message["text"])

    async def to_browser():
        async for message in upstream:
            if message.type == aiohttp.WSMsgType.BINARY:
                await websocket.send_bytes(message.data)
            elif message.type == aiohttp.WSMsgType.TEXT:
                await websocket.send_text(message.data)
            else:
                return

    tasks = [asyncio.create_task(to_upstream()), asyncio.create_task(to_browser())]
    try:
        await asyncio.wait(tasks, timeout=LIVE_MAX_SECONDS, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await upstream.close()
        await _close(websocket, 1000)


async def _close(websocket: WebSocket, code: int) -> None:
    try:
        await websocket.close(code=code)
    except RuntimeError:
        pass
