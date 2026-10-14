"""
dosing.py

Produits de dosage (calculateur) : effet d'une dose sur un paramètre pour un
volume donné, ex. « 1 g de bicarbonate dans 100 L : +0,33 °dKH ». L'article du
stock lié est décompté quand un dosage est appliqué.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from middleware.database import Base


class DosingProduct(Base):
    __tablename__ = "dosing_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    brand: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    # Paramètre d'eau concerné (nom : KH, Ca, Mg, NO3, PO4...)
    parameter: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # Dose de référence : quantité et unité (mL, g, gouttes...)
    dose_amount: Mapped[float] = mapped_column(Float, nullable=False, default=1)
    dose_unit: Mapped[str] = mapped_column(String(20), nullable=False, default="mL")
    # Hausse du paramètre (dans son unité) pour cette dose dans per_volume_l litres
    raises: Mapped[float] = mapped_column(Float, nullable=False)
    per_volume_l: Mapped[float] = mapped_column(Float, nullable=False, default=100)
    # Produit décrit par sa concentration (oligo-éléments, solution maison) : gardée pour
    # l'affichage et la modification ; « raises » en est calculé par l'interface
    concentration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    concentration_unit: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    inventory_item_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)
