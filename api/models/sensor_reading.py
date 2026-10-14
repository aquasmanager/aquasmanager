"""
Mesures enregistrées des capteurs.
"""

from datetime import datetime
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import Integer, ForeignKey, Float, DateTime, Index
from middleware.database import Base



class SensorReading(Base):
    """Mesure d'un capteur à un instant (historique des courbes)."""

    __tablename__ = "sensors_reading"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    sensor_id: Mapped[int] = mapped_column(Integer, ForeignKey("sensors.id", ondelete="CASCADE"), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # RELATIONS CORRIGÉES AU SINGULIER
    sensor: Mapped["Sensor"] = relationship(back_populates="readings")

    __table_args__ = (Index("ix_sensors_reading_sensor_ts", "sensor_id", "timestamp"),)