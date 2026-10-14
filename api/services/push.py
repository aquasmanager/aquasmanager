"""
push.py

Notifications Web Push (téléphone, ordinateur) aux appareils abonnés.
La clé VAPID est générée au premier démarrage et gardée à côté de la base
(comme la clé secrète) sauf si elle est fournie (push.vapid_private_key).
Les envois partent dans un thread : une alerte MQTT n'attend pas le réseau.
"""

import base64
import json
import logging
import threading
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

from middleware.database import SessionLocal
from models.push_subscription import PushSubscription
from settings import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def vapid() -> Vapid:
    if settings.push.vapid_private_key:
        return Vapid.from_pem(settings.push.vapid_private_key.encode())
    key_file = Path(settings.database.sqlite_path).resolve().parent / ".vapid_private.pem"
    if key_file.exists():
        return Vapid.from_file(str(key_file))
    key = Vapid()
    key.generate_keys()
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key.save_key(str(key_file))
    key_file.chmod(0o600)
    return key


def public_key() -> str:
    """Clé publique au format attendu par PushManager.subscribe (base64url, point non compressé)."""
    raw = vapid().public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _send(subscriptions: list[tuple[int, dict]], payload: str) -> None:
    expired: list[int] = []
    for sub_id, info in subscriptions:
        try:
            webpush(
                subscription_info=info,
                data=payload,
                vapid_private_key=vapid(),
                vapid_claims={"sub": settings.push.contact},
                timeout=10,
                ttl=3600,
            )
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):
                expired.append(sub_id)  # abonnement révoqué côté navigateur
            else:
                logger.warning("Notification push refusée (%s) : %s", status, e)
        except Exception:
            logger.exception("Envoi de notification push impossible")
    if expired:
        db = SessionLocal()
        try:
            db.query(PushSubscription).filter(PushSubscription.id.in_(expired)).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


def send_push(title: str, body: str, url: str = "/home", user_id: int | None = None, wait: bool = False) -> int:
    """Envoie à tous les appareils abonnés (ou à ceux d'un utilisateur). Renvoie le nombre d'appareils visés."""
    if not settings.push.enabled:
        return 0
    db = SessionLocal()
    try:
        query = db.query(PushSubscription)
        if user_id is not None:
            query = query.filter(PushSubscription.user_id == user_id)
        subscriptions = [
            (s.id, {"endpoint": s.endpoint, "keys": {"p256dh": s.p256dh, "auth": s.auth}}) for s in query.all()
        ]
    finally:
        db.close()
    if not subscriptions:
        return 0
    payload = json.dumps({"title": title, "body": body[:500], "url": url})
    if wait:
        _send(subscriptions, payload)
    else:
        threading.Thread(target=_send, args=(subscriptions, payload), daemon=True).start()
    return len(subscriptions)
