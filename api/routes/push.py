"""
push.py (routes)

Abonnement de l'appareil courant aux notifications push.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from middleware.auth import min_role_required
from middleware.database import get_db
from models.push_subscription import PushSubscription
from services.push import public_key, send_push

router = APIRouter(prefix="/push", tags=["push"])


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=200)
    auth: str = Field(min_length=4, max_length=100)


class SubscriptionIn(BaseModel):
    endpoint: str = Field(pattern=r"^https://", max_length=1000)
    keys: SubscriptionKeys


class Unsubscribe(BaseModel):
    endpoint: str


@router.get("/public-key")
def get_public_key():
    return {"public_key": public_key()}


@router.post("/subscriptions", status_code=status.HTTP_201_CREATED)
def subscribe(
    sub: SubscriptionIn,
    request: Request,
    identity: dict = Depends(min_role_required("consult")),
    db: Session = Depends(get_db),
):
    existing: Optional[PushSubscription] = db.query(PushSubscription).filter(PushSubscription.endpoint == sub.endpoint).first()
    record = existing or PushSubscription(endpoint=sub.endpoint)
    record.user_id = identity.get("user_id")
    record.p256dh = sub.keys.p256dh
    record.auth = sub.keys.auth
    record.user_agent = (request.headers.get("user-agent") or "")[:200]
    db.add(record)
    db.commit()
    return {"ok": True}


@router.post("/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(
    payload: Unsubscribe,
    _: dict = Depends(min_role_required("consult")),
    db: Session = Depends(get_db),
):
    db.query(PushSubscription).filter(PushSubscription.endpoint == payload.endpoint).delete()
    db.commit()


@router.post("/test")
def test(identity: dict = Depends(min_role_required("consult"))):
    count = send_push(
        "AquasManager", "Les notifications fonctionnent sur cet appareil.", "/home", user_id=identity.get("user_id")
    )
    return {"devices": count}
