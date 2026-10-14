"""
inventory.py

Stock de consommables (sel, résine déionisante, KH+...) pour savoir quand
en racheter. Chaque ajustement (réappro/consommation) est journalisé
(InventoryMovement) pour garder une trace ("acheté X le...").
"""

from typing import TYPE_CHECKING, Optional, List
from datetime import date, datetime

from sqlalchemy import Column, Date, Integer, String, Float, ForeignKey, TIMESTAMP, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from middleware.database import Base

if TYPE_CHECKING:
    from models.aquarium import Aquarium



# Aquariums concernés par un article partagé (portée « multiple »)
inventory_item_aquariums = Table(
    "inventory_item_aquariums",
    Base.metadata,
    Column("item_id", Integer, ForeignKey("inventory_items.id", ondelete="CASCADE"), primary_key=True),
    Column("aquarium_id", Integer, ForeignKey("aquariums.id", ondelete="CASCADE"), primary_key=True),
)


class InventoryItem(Base):
    """Article du stock (sel, réactif, nourriture...) avec seuil d'alerte."""

    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    aquarium_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aquariums.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Portée : « single » (aquarium_id seul), « multiple » (linked_aquariums)
    # ou « all » (tous les aquariums, y compris les futurs). aquarium_id reste
    # l'aquarium de rattachement (création, alertes).
    scope: Mapped[str] = mapped_column(String(10), nullable=False, default="single")
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    low_stock_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Date d'ouverture du conditionnement en cours (réactif de test, bidon...)
    opened_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)

    movements: Mapped[List["InventoryMovement"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="InventoryMovement.created_at"
    )
    linked_aquariums: Mapped[List["Aquarium"]] = relationship(secondary=inventory_item_aquariums)

    @property
    def aquarium_ids(self) -> list[int]:
        """Aquariums concernés ([] = tous)."""
        if self.scope == "all":
            return []
        if self.scope == "multiple":
            return sorted(a.id for a in self.linked_aquariums)
        return [self.aquarium_id]


class InventoryMovement(Base):
    """
    Mouvement du stock d'un article.

    delta positif = réappro, négatif = consommation.
    """

    __tablename__ = "inventory_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    delta: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)

    item: Mapped["InventoryItem"] = relationship(back_populates="movements")
