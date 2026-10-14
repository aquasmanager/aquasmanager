"""
journal.py

Journal de bord d'un aquarium : notes datées (« ajout de 2 Acropora »,
« algues sur la vitre ») affichées aussi sur les courbes des paramètres,
pour relier causes et effets. Certaines sont écrites automatiquement
(ajout d'un vivant, maintenance).
"""

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from middleware.database import Base

CATEGORIES = ("note", "livestock", "maintenance", "water_change", "dosing", "problem")


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    aquarium_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aquariums.id", ondelete="CASCADE"), nullable=False, index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now, index=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False, default="note")
    text: Mapped[str] = mapped_column(String(500), nullable=False)
    # Écrite par l'appli (ajout d'un vivant, maintenance) plutôt que saisie
    auto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)
