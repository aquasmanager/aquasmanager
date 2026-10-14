"""
license.py

Licence de l'installation (une seule ligne) : clé collée par un
administrateur et identifiant d'installation (pour une clé réservée à
une installation précise).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import TIMESTAMP, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from middleware.database import Base


class AppLicense(Base):
    __tablename__ = "app_license"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Clé signée « AQM1.<données>.<signature> » ; vide = pas de licence
    license_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Identifiant de cette installation, créé au premier démarrage
    instance_id: Mapped[str] = mapped_column(String(36), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)
