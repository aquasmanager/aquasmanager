"""
water_parameter.py

Paramètres d'eau suivis manuellement (KH, NO3, PO4, Ca...) : contrairement
aux Sensor, il n'y a pas de capteur physique (controller_id/pin_id) associé,
les valeurs sont saisies à la main par l'utilisateur au fil du temps.
"""

from typing import Optional, List
from datetime import datetime

from sqlalchemy import Integer, String, Float, ForeignKey, TIMESTAMP, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.schema import UniqueConstraint

from middleware.database import Base



class WaterParameter(Base):
    """Paramètre d'eau suivi manuellement (KH, NO3, Ca...) avec sa plage cible."""

    __tablename__ = "water_parameters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    aquarium_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aquariums.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(30), nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    target_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Épinglage manuel en haut de la grille (choix utilisateur, pas une
    # liste figée de noms côté client).
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)
    # Dernière alerte préventive de tendance (évite de la répéter à chaque évaluation)
    trend_alerted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)

    aquarium: Mapped["Aquarium"] = relationship(back_populates="water_parameters")
    readings: Mapped[List["WaterParameterReading"]] = relationship(
        back_populates="parameter", cascade="all, delete-orphan", order_by="WaterParameterReading.timestamp"
    )

    __table_args__ = (UniqueConstraint("aquarium_id", "name", name="check_water_parameter_aquarium_name_unique"),)

    @property
    def last_value(self) -> Optional[float]:
        return self.readings[-1].value if self.readings else None

    @property
    def last_reading_at(self) -> Optional[datetime]:
        return self.readings[-1].timestamp if self.readings else None

    @property
    def full_name(self) -> Optional[str]:
        from services.water_parameter_defaults import full_name_for

        return full_name_for(self.name)

    @property
    def in_target(self) -> Optional[bool]:
        """None si pas de relevé ou pas de cible."""
        value = self.last_value
        if value is None or (self.target_min is None and self.target_max is None):
            return None
        return (self.target_min is None or value >= self.target_min) and (
            self.target_max is None or value <= self.target_max
        )


class WaterParameterReading(Base):
    """Relevé d'un paramètre d'eau (valeur, date, note, test ICP d'origine)."""

    __tablename__ = "water_parameter_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    water_parameter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("water_parameters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)
    # Renseigné uniquement pour un relevé issu d'un import ICP : permet de
    # regrouper tous les paramètres d'un même test pour le comparer à un
    # autre test ultérieur (évolution entre deux analyses).
    icp_batch_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("icp_import_batches.id", ondelete="SET NULL"), nullable=True, index=True
    )

    parameter: Mapped["WaterParameter"] = relationship(back_populates="readings")
    icp_batch: Mapped[Optional["IcpImportBatch"]] = relationship(back_populates="readings")


class IcpImportBatch(Base):
    """
    Test ICP importé.

    Un "test ICP" : un import = un labo + une date de prélèvement. Les
    relevés qui en découlent (un par paramètre présent dans le rapport)
    pointent vers ce batch, ce qui permet de comparer deux tests entre eux
    sans avoir à deviner un regroupement à partir des dates/notes.
    """

    __tablename__ = "icp_import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    aquarium_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aquariums.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lab: Mapped[str] = mapped_column(String(30), nullable=False)
    sample_date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)
    # Nom d'origine du rapport ; le fichier est stocké dans uploads/icp/<id>.pdf
    pdf_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    readings: Mapped[List["WaterParameterReading"]] = relationship(back_populates="icp_batch")
