"""
notification_settings.py

Canal des alertes (Telegram, ntfy, les deux ou aucun), envoi par e-mail
(indépendant du choix précédent) et paramètres de chaque canal, modifiables
depuis l'interface. Une seule ligne (id = 1).
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import TIMESTAMP, Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from middleware.database import Base


class NotificationProvider(enum.Enum):
    none = "none"
    telegram = "telegram"
    ntfy = "ntfy"
    both = "both"


class NotificationSettings(Base):
    __tablename__ = "notification_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[NotificationProvider] = mapped_column(
        Enum(NotificationProvider), nullable=False, default=NotificationProvider.none
    )
    telegram_bot_token: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ntfy_url: Mapped[str] = mapped_column(String(300), nullable=False, default="https://ntfy.sh")
    ntfy_topic: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ntfy_token: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # E-mail (SMTP) ; smtp_security : starttls (port 587), ssl (port 465) ou none
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    smtp_host: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    smtp_security: Mapped[str] = mapped_column(String(10), nullable=False, default="starttls")
    smtp_user: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    smtp_password: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    email_from: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # Destinataires séparés par des virgules
    email_to: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now, onupdate=datetime.now)
