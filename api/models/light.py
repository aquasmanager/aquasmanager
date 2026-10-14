"""
light.py

Une lampe (rampe LED) pilotée par un contrôleur : chaque canal (couleur) est
une sortie PWM de l'ESP. Le programme horaire de chaque canal est exécuté par
l'ESP lui-même (voir services/light_firmware.py).
"""

from datetime import date
from typing import List, Optional

from sqlalchemy import DATE, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from middleware.database import Base


class Light(Base):
    __tablename__ = "lights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    aquarium_id: Mapped[int] = mapped_column(Integer, ForeignKey("aquariums.id"), nullable=False)
    controller_id: Mapped[int] = mapped_column(Integer, ForeignKey("controllers.id", ondelete="CASCADE"), nullable=False)
    # Unique par aquarium (services/naming.py)
    name: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # Fréquence PWM des sorties (Hz) : adaptée aux drivers LED à entrée PWM (type Meanwell LDD)
    pwm_frequency: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    # Clair de lune : intensité plancher (%) du canal choisi quand le programme est plus bas
    moonlight_channel_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    moonlight_intensity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Acclimatation : le programme est multiplié par un facteur qui passe de
    # acclimation_start_percent à 100 % en acclimation_days jours
    acclimation_start: Mapped[Optional[date]] = mapped_column(DATE, nullable=True)
    acclimation_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    acclimation_start_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    controller: Mapped["Controller"] = relationship(back_populates="lights")
    aquarium: Mapped["Aquarium"] = relationship(back_populates="lights")
    light_channels: Mapped[List["LightChannel"]] = relationship(
        back_populates="light", cascade="all, delete-orphan", order_by="LightChannel.id"
    )
