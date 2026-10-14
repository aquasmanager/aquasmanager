"""Aquarium model"""

import enum
from typing import List

from sqlalchemy.orm import relationship, mapped_column, Mapped
from typing import Optional

from sqlalchemy import Integer, String, DATE, Enum, JSON, TIMESTAMP
from middleware.database import Base
from datetime import datetime, date



class AquariumWaterType(enum.Enum):
    """Type d'eau d'un aquarium (mer ou douce)."""

    sea = "sea"
    pure = "pure"

    def __str__(self):
        return self.value


class Aquarium(Base):
    """Aquarium : caractéristiques, vivants, matériel, paramètres d'eau et mode maintenance."""

    __tablename__ = "aquariums"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    name: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)

    date_creation: Mapped[date] = mapped_column(DATE, nullable=False, default=date.today)

    volume: Mapped[int] = mapped_column(Integer, nullable=False)

    water_type: Mapped[AquariumWaterType] = mapped_column(Enum(AquariumWaterType, validate_strings=True), nullable=False)

    biotope: Mapped[str] = mapped_column(String(30), nullable=False)

    # Mode maintenance (changement d'eau...) : équipements choisis arrêtés jusqu'à
    # maintenance_until, puis remis dans leur mode et état d'avant (maintenance_saved_modes)
    maintenance_until: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    maintenance_started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    # Dernière sélection d'équipements (proposée la fois suivante)
    maintenance_equipment_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # {id d'équipement: {mode, status} d'avant}, pendant la maintenance seulement
    maintenance_saved_modes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    corals: Mapped[List["Coral"]] = relationship(back_populates="aquarium", cascade="all, delete-orphan")
    plants: Mapped[List["Plant"]] = relationship(back_populates="aquarium", cascade="all, delete-orphan")
    fishes: Mapped[List["Fish"]] = relationship(back_populates="aquarium", cascade="all, delete-orphan")
    equipments: Mapped[List["Equipment"]] = relationship(back_populates="aquarium", cascade="all, delete-orphan")
    sensors: Mapped[List["Sensor"]] = relationship(back_populates="aquarium", cascade="all, delete-orphan")
    invertebrates: Mapped[List["Invertebrate"]] = relationship(back_populates="aquarium", cascade="all, delete-orphan")
    lights: Mapped[List["Light"]] = relationship(back_populates="aquarium", cascade="all, delete-orphan")
    cameras: Mapped[List["Camera"]] = relationship(back_populates="aquarium", cascade="all, delete-orphan", order_by="Camera.sort_order")
    dashboard_cards: Mapped[List["DashboardCard"]] = relationship(back_populates="aquarium", cascade="all, delete-orphan")
    water_parameters: Mapped[List["WaterParameter"]] = relationship(back_populates="aquarium", cascade="all, delete-orphan")