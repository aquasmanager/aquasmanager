"""
Coraux des aquariums.
"""

from typing import Optional
import enum
from datetime import date
from sqlalchemy.orm import relationship, Mapped, mapped_column, validates
from sqlalchemy import Integer, String, DATE, Enum, ForeignKey, JSON

from middleware.database import Base



class CoralType(enum.Enum):
    """Famille de corail : SPS (petits polypes), LPS (grands polypes), mou."""

    LPS = "LPS"
    SPS = "SPS"
    MOU = "MOU"

    def __str__(self):
        return self.value


class Coral(Base):
    """Corail d'un aquarium : espèce, besoins (lumière, brassage), provenance et n° CITES."""

    __tablename__ = "corals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    aquarium_id: Mapped[int] = mapped_column(Integer, ForeignKey("aquariums.id"), nullable=False)

    # Utilisation moderne de Mapped au lieu de Column pour l'uniformité
    name: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # Nombre d'individus / de colonies (ex : un banc de 5 poissons)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cites: Mapped[str] = mapped_column(String(30), nullable=False)

    date_acquisition: Mapped[date] = mapped_column(DATE, nullable=False, default=date.today)

    type: Mapped[CoralType] = mapped_column(Enum(CoralType, validate_strings=True), nullable=False)

    scientific_name: Mapped[str] = mapped_column(String(30), nullable=False)
    family: Mapped[str] = mapped_column(String(30), nullable=True)
    origin: Mapped[str] = mapped_column(String(30), nullable=True)
    # Provenance : où le corail a été acquis (magasin, bourse, particulier) — traçabilité CITES
    acquired_from: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    light_range: Mapped[dict] = mapped_column(JSON, nullable=False)
    brewing_range: Mapped[dict] = mapped_column(JSON, nullable=False)
    aggressiveness_level: Mapped[int] = mapped_column(Integer, nullable=False)
    resistance_level: Mapped[int] = mapped_column(Integer, nullable=False)
    location_level: Mapped[int] = mapped_column(Integer, nullable=False)

    aquarium: Mapped["Aquarium"] = relationship(back_populates="corals")

    @validates("type")
    def validate_type(self, key, value):
        if isinstance(value, CoralType):
            return value
        if isinstance(value, str) and value in CoralType._member_map_:
            return CoralType(value)
        raise ValueError(f"Type invalide: {value}")