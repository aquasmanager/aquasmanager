"""
equipment_usage.py

Usure et consommation des équipements : puissance, compteur cumulé
d'heures de fonctionnement (l'historique des activations est purgé au bout
de quelques mois), entretien périodique (ex : ampoule UV toutes les 9000 h).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import TIMESTAMP, Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from middleware.database import Base


class EquipmentUsage(Base):
    __tablename__ = "equipment_usage"

    equipment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equipments.id", ondelete="CASCADE"), primary_key=True
    )
    power_watts: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Secondes de fonctionnement cumulées (activations terminées)
    runtime_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    service_interval_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    service_label: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    # Compteur au dernier entretien, date, et tâche déjà créée pour ce cycle
    runtime_at_service: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    serviced_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    service_task_created: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class EnergySettings(Base):
    __tablename__ = "energy_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Prix du kWh (€), pour estimer le coût de l'électricité
    price_per_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.25)
