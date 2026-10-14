"""
invertebrate.py

Invertébrés d'un aquarium (crevettes, escargots, oursins...). Anciennement
« other_alives » : la table est renommée au démarrage (main.py).
"""

from datetime import date

from sqlalchemy import DATE, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from middleware.database import Base


class Invertebrate(Base):
    __tablename__ = "invertebrates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    aquarium_id: Mapped[int] = mapped_column(Integer, ForeignKey("aquariums.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # Nombre d'individus / de colonies (ex : un banc de 5 poissons)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # date.today sans parenthèses : évalué à l'insertion
    date_acquisition: Mapped[date] = mapped_column(DATE, nullable=False, default=date.today)
    scientific_name: Mapped[str] = mapped_column(String(30), nullable=False)
    family: Mapped[str] = mapped_column(String(30), nullable=True)
    origin: Mapped[str] = mapped_column(String(30), nullable=True)

    aquarium: Mapped["Aquarium"] = relationship(back_populates="invertebrates")  # noqa: F821
