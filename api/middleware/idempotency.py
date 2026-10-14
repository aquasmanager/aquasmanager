"""
Idempotence des écritures : l'appli hors connexion rejoue ses requêtes avec un
en-tête Idempotency-Key. Si la clé est connue, la réponse d'origine est
renvoyée sans refaire l'action (pas de relevé ni de vente en double quand la
première réponse s'est perdue en route).

Middleware ASGI pur (la réponse doit être lue pour être mémorisée). Ne sont pas
mémorisées : les erreurs serveur (5xx), pour pouvoir réessayer, ni les
redirections (3xx) : POST /sensors est redirigé vers /sensors/ et le navigateur
rejoue la requête avec la même clé, qui doit encore être libre.
"""

import logging
from datetime import datetime, timedelta

from starlette.concurrency import run_in_threadpool

from middleware.database import SessionLocal
from models.idempotency import IdempotencyRecord

logger = logging.getLogger(__name__)

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
KEY_MAX_LENGTH = 100
RETENTION_DAYS = 14


def _same_path(a: str, b: str) -> bool:
    """/sensors et /sensors/ désignent la même ressource."""
    return a.rstrip("/") == b.rstrip("/")


def _load(key: str):
    db = SessionLocal()
    try:
        record = db.get(IdempotencyRecord, key)
        if record is None:
            return None
        return record.method, record.path, record.status_code, record.content_type, record.body
    finally:
        db.close()


def _store(key: str, method: str, path: str, status: int, content_type: str, body: bytes) -> None:
    db = SessionLocal()
    try:
        db.merge(
            IdempotencyRecord(key=key, method=method, path=path[:255], status_code=status, content_type=content_type, body=body)
        )
        db.commit()
    except Exception:
        logger.exception("Mémorisation de la clé d'idempotence impossible")
        db.rollback()
    finally:
        db.close()


def purge_idempotency_keys() -> int:
    db = SessionLocal()
    try:
        limit = datetime.now() - timedelta(days=RETENTION_DAYS)
        deleted = db.query(IdempotencyRecord).filter(IdempotencyRecord.created_at < limit).delete()
        db.commit()
        return deleted
    finally:
        db.close()


class IdempotencyMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in WRITE_METHODS:
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers") or [])
        key = headers.get(b"idempotency-key", b"").decode("latin-1").strip()
        if not key or len(key) > KEY_MAX_LENGTH:
            return await self.app(scope, receive, send)

        stored = await run_in_threadpool(_load, key)
        if stored is not None:
            method, path, status, content_type, body = stored
            if method != scope["method"] or not _same_path(path, scope["path"][:255]):
                # Même clé pour une autre requête : refus plutôt que mauvaise réponse
                status, content_type = 422, "application/json"
                body = b'{"detail":"Cle d\'idempotence deja utilisee pour une autre requete."}'
            await send({
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", content_type.encode()), (b"idempotent-replay", b"true")],
            })
            await send({"type": "http.response.body", "body": body})
            return

        response: dict = {"status": 500, "content_type": "application/json", "body": []}

        async def capture(message):
            if message["type"] == "http.response.start":
                response["status"] = message["status"]
                for name, value in message.get("headers", []):
                    if name.lower() == b"content-type":
                        response["content_type"] = value.decode("latin-1")
            elif message["type"] == "http.response.body":
                response["body"].append(message.get("body", b""))
            await send(message)

        await self.app(scope, receive, capture)
        if response["status"] < 300 or 400 <= response["status"] < 500:
            await run_in_threadpool(
                _store, key, scope["method"], scope["path"], response["status"], response["content_type"],
                b"".join(response["body"]),
            )
