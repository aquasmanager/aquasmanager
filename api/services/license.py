"""
license.py

Licence de l'installation : certaines fonctionnalités ne s'ouvrent qu'avec
une clé signée par l'éditeur (Ed25519). L'appli ne contacte aucun serveur :
la clé porte elle-même ce qu'elle autorise, et sa signature se vérifie avec
la clé publique ci-dessous. Toute modification de la clé casse la signature.

Format : « AQM1.<données JSON en base64url>.<signature base64url> », la
signature portant sur « AQM1.<données> ». Données :
    {"v": 1, "id": "…", "client": "…", "features": ["bourse"],
     "issued": "2026-09-29", "expires": null | "AAAA-MM-JJ",
     "instance": null | "<identifiant d'installation>"}

Sans clé valide : toutes les fonctionnalités sauf celles de PAID_FEATURES.
Ce qui tourne déjà (règles, capteurs, équipements) n'est jamais concerné.
"""

import base64
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from middleware.database import SessionLocal
from models.license import AppLicense
from settings import settings

logger = logging.getLogger(__name__)

PREFIX = "AQM1"

# Clés publiques de l'éditeur (base64, 32 octets). La clé privée n'est pas
# dans le dépôt ; en ajouter une ici permet de la renouveler sans invalider
# les licences déjà émises.
PUBLIC_KEYS = ["O3u9CTnBVeuBvPXAsBy+iiVNFqjaRm8u8UY0oYFaPFc="]

# Fonctionnalités réservées à une licence (les autres sont ouvertes à tous)
PAID_FEATURES = {
    "bourse": "Bourse : vente de boutures, cessions et certificats, vitrine",
    "assistant": "Assistant IA",
}

_CACHE_SECONDS = 60


class LicenseError(ValueError):
    """Clé illisible, mal signée ou non applicable à cette installation."""


@dataclass
class LicenseStatus:
    instance_id: str
    features: list[str] = field(default_factory=list)
    valid: bool = False
    source: Optional[str] = None  # "app" (collée dans l'appli) ou "env" (variable)
    license_id: Optional[str] = None
    client: Optional[str] = None
    issued: Optional[str] = None
    expires: Optional[str] = None
    error: Optional[str] = None

    def has(self, feature: str) -> bool:
        return feature not in PAID_FEATURES or feature in self.features


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def decode_key(key: str, instance_id: str, today: Optional[date] = None) -> dict:
    """Vérifie la clé et renvoie ses données ; LicenseError sinon."""
    parts = key.strip().split(".")
    if len(parts) != 3 or parts[0] != PREFIX:
        raise LicenseError("Clé de licence illisible")
    signed = f"{parts[0]}.{parts[1]}".encode()
    try:
        signature = _b64decode(parts[2])
    except ValueError as exc:
        raise LicenseError("Clé de licence illisible") from exc
    for public_key in PUBLIC_KEYS:
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key)).verify(signature, signed)
            break
        except InvalidSignature:
            continue
    else:
        raise LicenseError("Signature de la clé invalide")
    try:
        data = json.loads(_b64decode(parts[1]))
    except (ValueError, json.JSONDecodeError) as exc:
        raise LicenseError("Clé de licence illisible") from exc
    if not isinstance(data, dict) or data.get("v") != 1 or not isinstance(data.get("features"), list):
        raise LicenseError("Version de clé non prise en charge")
    if data.get("instance") and data["instance"] != instance_id:
        raise LicenseError("Clé prévue pour une autre installation")
    expires = data.get("expires")
    if expires and date.fromisoformat(expires) < (today or date.today()):
        raise LicenseError(f"Licence expirée le {expires}")
    return data


def license_row(db: Session) -> AppLicense:
    row = db.get(AppLicense, 1)
    if row is None:
        row = AppLicense(id=1, instance_id=str(uuid.uuid4()), updated_at=datetime.now())
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def compute_status(db: Session) -> LicenseStatus:
    row = license_row(db)
    # Clé collée dans l'appli, sinon variable d'environnement (AQUAS_LICENSE_KEY)
    key, source = (row.license_key, "app") if row.license_key else (settings.license_key.strip(), "env")
    result = LicenseStatus(instance_id=row.instance_id)
    if not key:
        return result
    result.source = source
    try:
        data = decode_key(key, row.instance_id)
    except LicenseError as exc:
        result.error = str(exc)
        return result
    result.valid = True
    result.features = [f for f in data["features"] if isinstance(f, str)]
    result.license_id = data.get("id")
    result.client = data.get("client")
    result.issued = data.get("issued")
    result.expires = data.get("expires")
    return result


_cache: tuple[float, Optional[LicenseStatus]] = (0.0, None)


def invalidate_cache():
    global _cache
    _cache = (0.0, None)


def current_status() -> LicenseStatus:
    """Statut en cache (une minute) : vérifié au plus une fois par minute."""
    global _cache
    at, cached = _cache
    if cached is not None and time.monotonic() - at < _CACHE_SECONDS:
        return cached
    with SessionLocal() as db:
        cached = compute_status(db)
    _cache = (time.monotonic(), cached)
    return cached


def has_feature(feature: str) -> bool:
    return current_status().has(feature)


def require_feature(feature: str):
    """Dépendance FastAPI : 403 si la fonctionnalité n'est pas ouverte par la licence."""

    def dependency():
        if not has_feature(feature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Fonctionnalité non disponible sans licence : {PAID_FEATURES.get(feature, feature)}",
                headers={"X-Aquas-Feature": feature},
            )

    return dependency
