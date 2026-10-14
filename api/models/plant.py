"""
Plantes des aquariums.
"""

import enum
from datetime import date
from sqlalchemy.orm import relationship, Mapped, mapped_column, validates
from sqlalchemy import Integer, String, DATE, Enum, ForeignKey, JSON

from middleware.database import Base



class PlantGrowing(enum.Enum):
    """Vitesse de croissance d'une plante."""

    slow = "slow"
    average = "average"
    fast = "fast"

    def __str__(self):
        return self.value


class PlantLocation(enum.Enum):
    """Emplacement conseillé d'une plante dans le bac."""

    front = "front"
    middle = "middle"
    back = "back"

    def __str__(self):
        return self.value


class Plant(Base):
    """Plante d'un aquarium d'eau douce : besoins (lumière, température), croissance, emplacement."""

    __tablename__ = "plants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    aquarium_id: Mapped[int] = mapped_column(Integer, ForeignKey("aquariums.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # Nombre d'individus / de colonies (ex : un banc de 5 poissons)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    scientific_name: Mapped[str] = mapped_column(String(30), nullable=False)
    family: Mapped[str] = mapped_column(String(30), nullable=False)
    origin: Mapped[str] = mapped_column(String(30), nullable=False)
    light_range: Mapped[dict] = mapped_column(JSON, nullable=False)
    temperature_range: Mapped[dict] = mapped_column(JSON, nullable=False)

    growing: Mapped[PlantGrowing] = mapped_column(Enum(PlantGrowing, validate_strings=True), nullable=False)

    resistance_level: Mapped[int] = mapped_column(Integer, nullable=False)
    max_height: Mapped[int] = mapped_column(Integer, nullable=False)

    location: Mapped[PlantLocation] = mapped_column(Enum(PlantLocation, validate_strings=True), nullable=False)

    date_acquisition: Mapped[date] = mapped_column(DATE, nullable=False, default=date.today)

    # RELATIONS CORRIGÉES AU SINGULIER
    aquarium: Mapped["Aquarium"] = relationship(back_populates="plants")

    @validates("growing")
    def validate_growing(self, key, value):
        if isinstance(value, PlantGrowing):
            return value
        if isinstance(value, str) and value in PlantGrowing._member_map_:
            return PlantGrowing(value)
        raise ValueError(f"Growing invalide: {value}")

    @validates("location")
    def validate_location(self, key, value):
        if isinstance(value, PlantLocation):
            return value
        if isinstance(value, str) and value in PlantLocation._member_map_:
            return PlantLocation(value)
        raise ValueError(f"Location invalide: {value}")