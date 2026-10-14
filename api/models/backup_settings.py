"""
backup_settings.py

Réglages des sauvegardes (une seule ligne) : sauvegarde automatique et sa
fréquence, contenu, destination (dossier local ou dossier externe, par
exemple un partage NFS monté par l'hôte), dernier passage.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import TIMESTAMP, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from middleware.database import Base


class BackupSettings(Base):
    __tablename__ = "backup_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # "daily" ou "weekly" ; heure locale ; jour (0 = lundi) pour l'hebdomadaire
    frequency: Mapped[str] = mapped_column(String(10), nullable=False, default="daily")
    hour: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Sauvegardes automatiques gardées (les plus récentes)
    keep_count: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    # Contenu (la base est toujours incluse)
    include_photos: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    include_icp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    include_documents: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    include_certificates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # "local" (volume de l'application) ou "external" (dossier monté, ex. NFS)
    destination: Mapped[str] = mapped_column(String(10), nullable=False, default="local")
    external_path: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    last_status: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    last_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
