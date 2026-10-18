"""
notification_settings.py (routes)

Choix du canal d'alerte (Telegram, ntfy, les deux, aucun), e-mail et test
d'envoi. Réservé aux administrateurs ; jetons et mot de passe SMTP ne sont
jamais renvoyés.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from middleware.auth import min_role_required
from middleware.database import get_db
from models.notification_settings import NotificationSettings
from schemas.notification_settings import (
    NotificationSettingsRead,
    NotificationSettingsUpdate,
    NotificationTestRequest,
    NotificationTestResult,
)
from services.notify import active_channels, get_notification_settings, send_on_channels

router = APIRouter(
    prefix="/notification-settings", tags=["notifications"], dependencies=[Depends(min_role_required("admin"))]
)


def _read(conf: NotificationSettings) -> dict:
    return {
        "provider": conf.provider,
        "telegram_chat_id": conf.telegram_chat_id,
        "telegram_bot_token_set": bool(conf.telegram_bot_token),
        "ntfy_url": conf.ntfy_url,
        "ntfy_topic": conf.ntfy_topic,
        "ntfy_token_set": bool(conf.ntfy_token),
        "email_enabled": bool(conf.email_enabled),
        "smtp_host": conf.smtp_host,
        "smtp_port": conf.smtp_port or 587,
        "smtp_security": conf.smtp_security or "starttls",
        "smtp_user": conf.smtp_user,
        "smtp_password_set": bool(conf.smtp_password),
        "email_from": conf.email_from,
        "email_to": conf.email_to,
    }


@router.get("/", response_model=NotificationSettingsRead)
def read_notification_settings(db: Session = Depends(get_db)):
    return _read(get_notification_settings(db))


@router.put("/", response_model=NotificationSettingsRead)
def update_notification_settings(update: NotificationSettingsUpdate, db: Session = Depends(get_db)):
    conf = get_notification_settings(db)
    for field, value in update.model_dump(exclude_unset=True).items():
        if field in ("provider", "email_enabled", "smtp_port", "smtp_security"):
            if value is not None:
                setattr(conf, field, value)
        elif field == "ntfy_url":
            if value:
                conf.ntfy_url = value
        else:
            # "" efface la valeur (ex : retirer un jeton)
            setattr(conf, field, value.strip() or None if value else None)
    if conf.email_enabled and not (conf.smtp_host and conf.email_to):
        db.rollback()
        raise HTTPException(status_code=422, detail="E-mail : indique le serveur SMTP et au moins un destinataire.")
    db.commit()
    db.refresh(conf)
    return _read(conf)


@router.post("/test", response_model=NotificationTestResult)
def send_test_notification(request: NotificationTestRequest, db: Session = Depends(get_db)):
    conf = get_notification_settings(db)
    channels = [request.channel] if request.channel else active_channels(conf)
    if not channels:
        raise HTTPException(status_code=400, detail="Aucun canal de notification actif.")
    results = send_on_channels(
        conf, channels, "[AquasManager] Notification de test", "Si tu lis ce message, les alertes arrivent bien."
    )
    return {"results": results}
