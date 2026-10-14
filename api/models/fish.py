"""
Poissons des aquariums.
"""

from datetime import date
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import Integer, String, DATE, ForeignKey, Boolean
from middleware.database import Base



class Fish(Base):
    """Poisson d'un aquarium (espèce, nombre, provenance)."""

    __tablename__ = "fishes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    aquarium_id: Mapped[int] = mapped_column(Integer, ForeignKey("aquariums.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # Nombre d'individus / de colonies (ex : un banc de 5 poissons)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    date_acquisition: Mapped[date] = mapped_column(DATE, nullable=False, default=date.today)

    scientific_name: Mapped[str] = mapped_column(String(30), nullable=False)
    family: Mapped[str] = mapped_column(String(30), nullable=True)
    origin: Mapped[str] = mapped_column(String(30), nullable=True)
    max_height: Mapped[int] = mapped_column(Integer, nullable=False)
    min_volume: Mapped[int] = mapped_column(Integer, nullable=False)
    reef_safe: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # RELATIONS CORRIGÉES AU SINGULIER
    aquarium: Mapped["Aquarium"] = relationship(back_populates="fishes")