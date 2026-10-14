"""
Programme horaire des lampes (points d'intensité par canal).
"""

from datetime import time
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import Integer, ForeignKey, Time
from middleware.database import Base



class LightSchedule(Base):
    """Point du programme d'un canal de lampe : intensité à une minute de la journée."""

    __tablename__ = "lights_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("lights_channels.id", ondelete="CASCADE"), nullable=False)
    schedule_time: Mapped[time] = mapped_column(Time(), nullable=False)
    intensity: Mapped[int] = mapped_column(Integer, nullable=False)

    # RELATIONS CORRIGÉES AU SINGULIER
    light_channel: Mapped["LightChannel"] = relationship(back_populates="schedules")