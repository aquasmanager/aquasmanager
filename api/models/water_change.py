"""
water_change.py

Changements d'eau : date, volume, sel utilisé (décompté du stock), tâche
d'entretien validée au passage ; une note est ajoutée au journal de bord.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from middleware.database import Base


class WaterChange(Base):
    __tablename__ = "water_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    aquarium_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aquariums.id", ondelete="CASCADE"), nullable=False, index=True
    )
    performed_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now, index=True)
    volume_l: Mapped[float] = mapped_column(Float, nullable=False)
    # Sel : article du stock et quantité dans l'unité de l'article (kg, g...)
    salt_item_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True
    )
    salt_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    journal_entry_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)
