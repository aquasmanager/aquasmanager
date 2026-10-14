"""
notification_settings.py

Canal des alertes (Telegram, ntfy, les deux ou aucun) et paramètres de
chaque canal, modifiables depuis l'interface. Une seule ligne (id = 1).
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import TIMESTAMP, Enum, Integer, String
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
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now, onupdate=datetime.now)
