"""
metric_alert.py

Alerte "hors cible" sur un paramètre d'eau manuel ou un capteur configuré
avec une cible (via une DashboardCard température/paramètre d'eau).
Volontairement séparé de EquipmentFault (défauts matériels remontés par
MQTT/ESPHome, système déjà en place et plus sensible à toucher) : même
logique de cycle de vie (created_at/resolved_at) mais une source différente
— une tâche périodique compare les valeurs courantes aux cibles configurées
plutôt qu'un événement matériel.
"""

import enum
from typing import Optional
from datetime import datetime

from sqlalchemy import Integer, String, Float, ForeignKey, TIMESTAMP, Enum, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from middleware.database import Base



class MetricAlertSource(enum.Enum):
    water_parameter = "water_parameter"
    sensor = "sensor"
    task_overdue = "task_overdue"
    low_stock = "low_stock"
    sensor_stale = "sensor_stale"

    def __str__(self):
        return self.value


class MetricAlert(Base):
    """Alerte ouverte puis résolue : paramètre ou capteur hors cible, sonde muette, tâche en retard, stock bas."""

    __tablename__ = "metric_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    aquarium_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aquariums.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[MetricAlertSource] = mapped_column(Enum(MetricAlertSource, validate_strings=True), nullable=False)

    # Un seul renseigné selon `source`, jamais plusieurs à la fois.
    water_parameter_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("water_parameters.id", ondelete="SET NULL"), nullable=True, index=True
    )
    dashboard_card_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("dashboard_cards.id", ondelete="SET NULL"), nullable=True, index=True
    )
    maintenance_task_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("maintenance_tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    inventory_item_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Sonde muette (sensor_stale)
    sensor_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sensors.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Copie du nom au moment de la détection : l'alerte reste lisible dans
    # l'historique même si le paramètre/la carte source est supprimé depuis.
    label: Mapped[str] = mapped_column(String(60), nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    initial_value: Mapped[float] = mapped_column(Float, nullable=False)
    resolved_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    # True si résolue via acquittement manuel plutôt que retour naturel dans
    # la cible : sert à ne pas rouvrir immédiatement une alerte acquittée
    # tant que la valeur n'a pas réellement changé (voir _sync_alert).
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Une notification d'ouverture a été envoyée : conditionne celle du retour à la normale
    notified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
