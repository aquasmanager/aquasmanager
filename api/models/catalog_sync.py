"""
catalog_sync.py

État de la synchronisation du catalogue commun d'espèces (une seule ligne) :
version reçue du hub de l'éditeur, date du dernier essai et résultat.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from middleware.database import Base


class CatalogSyncState(Base):
    __tablename__ = "catalog_sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Empreinte du catalogue appliqué (ETag du hub) : rien à faire s'il n'a pas changé
    etag: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Dernier résultat lisible (« 2 ajoutées, 1 mise à jour ») ou erreur
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
