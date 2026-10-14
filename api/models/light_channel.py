"""
Canaux d'une lampe pilotée (couleur, sortie PWM, plafond, clair de lune).
"""

import enum
from typing import List

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.sql.schema import UniqueConstraint

from middleware.database import Base


class ChannelMode(enum.Enum):
    AUTO = "AUTO"      # suit le programme horaire
    MANUAL = "MANUAL"  # intensité fixée depuis l'appli (current_intensity)
    OFF = "OFF"

    def __str__(self):
        return self.value


class LightChannel(Base):
    __tablename__ = "lights_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    light_id: Mapped[int] = mapped_column(Integer, ForeignKey("lights.id", ondelete="CASCADE"), nullable=False)
    pin_id: Mapped[int] = mapped_column(Integer, ForeignKey("controllers_pins.id", ondelete="RESTRICT"), nullable=False)
    # Couleur d'affichage (#rrggbb) et famille de spectre (profils prédéfinis)
    color: Mapped[str] = mapped_column(String(10), nullable=False, default="#ffffff")
    spectrum: Mapped[str] = mapped_column(String(20), nullable=False, default="other")
    mode: Mapped[ChannelMode] = mapped_column(Enum(ChannelMode, validate_strings=True), nullable=False, default=ChannelMode.AUTO)
    # Plafond (%) jamais dépassé, quel que soit le mode
    max_intensity: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    # Seuil (%) sous lequel le canal reste éteint : le driver ne passe jamais par sa
    # zone instable à faible intensité (scintillement au lever et au coucher)
    min_intensity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Intensité (%) du mode manuel
    current_intensity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inverted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Clair de lune : intensité plancher la nuit (0 = canal éteint la nuit) ; plusieurs
    # canaux possibles (ex. canal qui pilote le driver + canal bleu)
    moonlight_intensity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    light: Mapped["Light"] = relationship(back_populates="light_channels")
    pin: Mapped["ControllerPin"] = relationship(back_populates="lights_channel")
    schedules: Mapped[List["LightSchedule"]] = relationship(
        back_populates="light_channel", cascade="all, delete-orphan", order_by="LightSchedule.schedule_time"
    )

    __table_args__ = (UniqueConstraint("pin_id", name="check_light_channel_pin_unique"),)

    @validates("mode")
    def validate_mode(self, key, value):
        if isinstance(value, ChannelMode):
            return value
        if isinstance(value, str) and value in ChannelMode._member_map_:
            return ChannelMode(value)
        raise ValueError(f"Mode invalide: {value}")
