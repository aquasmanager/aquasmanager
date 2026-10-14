"""
Défauts signalés par les contrôleurs (osmolateur trop long, trop de cycles, sécurité...).
"""

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Boolean, ForeignKey, DateTime
from middleware.database import Base


class EquipmentFault(Base):
    """
    Défaut/alerte remonté par un contrôleur (topic MQTT .../fault ou .../notify).

    code: LEVEL_TIMEOUT, TOO_MANY_CYCLES, SENSOR_INTERLOCK, NOTIFY, OK
    latched: True seulement pour les anomalies internes de dosage
             (LEVEL_TIMEOUT / TOO_MANY_CYCLES) qui nécessitent un
             acquittement manuel. Les interlocks capteur (SENSOR_INTERLOCK)
             et les notifications simples se résolvent seuls.
    """

    __tablename__ = "equipment_faults"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    controller_id: Mapped[int] = mapped_column(ForeignKey("controllers.id", ondelete="CASCADE"), index=True)
    equipment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipments.id", ondelete="CASCADE"), nullable=True, index=True)

    code: Mapped[str] = mapped_column(String(30), index=True)
    message: Mapped[str] = mapped_column(Text)
    latched: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
