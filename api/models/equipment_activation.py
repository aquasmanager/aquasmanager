"""
equipment_activation.py

Journalise chaque transition OFF->ON->OFF d'un équipement (début, fin,
durée). Rempli par drivers/mqtt.py sur les changements d'état réels
(pas sur une republication du même état). Sert notamment aux
statistiques d'activité de la carte "Activité Osmolateur" du dashboard.
"""

from typing import Optional
from datetime import datetime

from sqlalchemy import Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from middleware.database import Base


class EquipmentActivation(Base):
    """Période de marche d'un équipement (début, fin) : historique et temps de fonctionnement."""

    __tablename__ = "equipment_activations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    equipment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equipments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    # NULL tant que l'activation est en cours (pas encore de transition OFF observée).
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    equipment: Mapped["Equipment"] = relationship(back_populates="activations")
