"""
notify.py

Envoi des alertes : notifications push, e-mail et, selon le canal choisi
dans l'interface (NotificationSettings), Telegram et/ou ntfy. L'e-mail se
règle dans l'interface ; à défaut, la section smtp du fichier de config sert
encore (installations antérieures). Appelé de façon
synchrone depuis le thread Paho (drivers/mqtt.py) : chaque canal est isolé
dans son propre try/except avec un timeout court pour qu'une panne d'un
canal ne bloque ni les autres ni le traitement MQTT.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from typing import Literal, Optional

import httpx
from sqlalchemy.orm import Session

from middleware.database import SessionLocal
from models.notification_settings import NotificationProvider, NotificationSettings
from settings import settings

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 10.0

Priority = Literal["low", "default", "high"]
# Échelle ntfy : 1 (min) à 5 (urgent)
_NTFY_PRIORITY = {"low": 2, "default": 3, "high": 4}


def _recipients(value: Optional[str]) -> list[str]:
    return [a.strip() for a in (value or "").replace(";", ",").split(",") if a.strip()]


def _smtp_send(host: str, port: int, security: str, user: Optional[str], password: Optional[str],
               sender: str, recipients: list[str], subject: str, body: str) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    smtp_class = smtplib.SMTP_SSL if security == "ssl" else smtplib.SMTP
    with smtp_class(host, port, timeout=_HTTP_TIMEOUT) as server:
        if security == "starttls":
            server.starttls()
        if user and password:
            server.login(user, password)
        server.sendmail(sender, recipients, msg.as_string())


def send_email_channel(conf: NotificationSettings, subject: str, message: str) -> None:
    """E-mail réglé dans l'interface ; lève une erreur lisible si la configuration est incomplète."""
    recipients = _recipients(conf.email_to)
    if not conf.smtp_host or not recipients:
        raise ValueError("E-mail : serveur SMTP ou destinataire manquant.")
    sender = conf.email_from or conf.smtp_user or recipients[0]
    _smtp_send(conf.smtp_host, conf.smtp_port or 587, conf.smtp_security or "starttls", conf.smtp_user,
               conf.smtp_password, sender, recipients, subject, message)


def send_email(subject: str, body: str) -> None:
    """E-mail de la section smtp du fichier de config (installations antérieures)."""
    conf = settings.smtp
    if not conf.enabled:
        return
    try:
        _smtp_send(conf.host, conf.port, "starttls" if conf.use_tls else "none", conf.user, conf.password,
                   conf.from_addr or conf.user, _recipients(conf.to_addr), subject, body)
        logger.info(f"Email d'alerte envoyé: {subject}")
    except Exception as e:
        logger.error(f"Échec envoi email d'alerte: {e}")


def send_telegram(conf: NotificationSettings, subject: str, message: str) -> None:
    if not conf.telegram_bot_token or not conf.telegram_chat_id:
        raise ValueError("Telegram : jeton du bot ou chat_id manquant.")
    resp = httpx.post(
        f"https://api.telegram.org/bot{conf.telegram_bot_token}/sendMessage",
        json={"chat_id": conf.telegram_chat_id, "text": f"{subject}\n{message}"},
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()


def send_ntfy(conf: NotificationSettings, subject: str, message: str, priority: Priority) -> None:
    if not conf.ntfy_topic:
        raise ValueError("ntfy : topic manquant.")
    headers = {"Authorization": f"Bearer {conf.ntfy_token}"} if conf.ntfy_token else {}
    # Publication JSON (et non via en-têtes) : le titre peut contenir des accents.
    resp = httpx.post(
        conf.ntfy_url.rstrip("/"),
        json={
            "topic": conf.ntfy_topic,
            "title": subject,
            "message": message,
            "priority": _NTFY_PRIORITY[priority],
            "tags": ["fish"],
        },
        headers=headers,
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()


def active_channels(conf: NotificationSettings) -> list[str]:
    channels = {
        NotificationProvider.none: [],
        NotificationProvider.telegram: ["telegram"],
        NotificationProvider.ntfy: ["ntfy"],
        NotificationProvider.both: ["telegram", "ntfy"],
    }[conf.provider]
    return channels + (["email"] if conf.email_enabled else [])


def send_on_channels(
    conf: NotificationSettings, channels: list[str], subject: str, message: str, priority: Priority = "default"
) -> dict[str, Optional[str]]:
    """Envoie sur chaque canal ; renvoie {canal: None si OK, sinon le message d'erreur}."""
    results: dict[str, Optional[str]] = {}
    for channel in channels:
        try:
            if channel == "telegram":
                send_telegram(conf, subject, message)
            elif channel == "email":
                send_email_channel(conf, subject, message)
            else:
                send_ntfy(conf, subject, message, priority)
            results[channel] = None
            logger.info(f"Notification {channel} envoyée")
        except Exception as e:
            error = _redact(conf, str(e))
            results[channel] = error
            logger.error(f"Échec envoi notification {channel}: {error}")
    return results


def _redact(conf: NotificationSettings, text: str) -> str:
    # Les erreurs httpx contiennent l'URL, donc le jeton du bot Telegram
    for secret in (conf.telegram_bot_token, conf.ntfy_token, conf.smtp_password):
        if secret:
            text = text.replace(secret, "***")
    return text


def get_notification_settings(db: Session) -> NotificationSettings:
    conf = db.get(NotificationSettings, 1)
    if conf is None:
        # Reprend l'ancienne configuration Telegram du fichier de config
        legacy = settings.telegram
        conf = NotificationSettings(
            id=1,
            provider=NotificationProvider.telegram if legacy.enabled else NotificationProvider.none,
            telegram_bot_token=legacy.bot_token or None,
            telegram_chat_id=legacy.chat_id or None,
        )
        db.add(conf)
        db.commit()
        db.refresh(conf)
    return conf


def dispatch_alert(subject: str, message: str, priority: Priority = "default") -> None:
    """Envoie l'alerte en notification push et sur les canaux choisis dans l'interface (e-mail compris)."""
    try:
        from services.push import send_push

        send_push(subject, message)
    except Exception as e:
        logger.error(f"Échec de l'envoi des notifications push: {e}")
    db = SessionLocal()
    try:
        conf = get_notification_settings(db)
        if not conf.email_enabled:
            send_email(subject, message)  # e-mail du fichier de config, s'il y en a un
        send_on_channels(conf, active_channels(conf), subject, message, priority)
    except Exception as e:
        logger.error(f"Échec de l'envoi des notifications: {e}")
    finally:
        db.close()
