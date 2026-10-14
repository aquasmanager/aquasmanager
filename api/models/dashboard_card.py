"""
dashboard_card.py

Configuration des cartes du dashboard, par aquarium. Persistée côté
serveur (et non en localStorage) pour rester cohérente entre appareils.
"""

import enum
from typing import Optional
from datetime import datetime

from sqlalchemy import Integer, String, Float, Enum, ForeignKey, JSON, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from middleware.database import Base


class DashboardCardType(enum.Enum):
    temperature = "temperature"
    water_param = "water_param"
    ro_reserve = "ro_reserve"
    binary_level = "binary_level"
    osmolator_events = "osmolator_events"
    # Raccourci de pilotage : marche / arrêt et mode auto / manuel
    equipment = "equipment"
    # Évolution combinée des paramètres d'eau (une par aquarium, créée d'office)
    water_trend = "water_trend"

    def __str__(self):
        return self.value


class DashboardCard(Base):
    """Carte du tableau de bord d'un aquarium (température, paramètre, niveau, pilotage...)."""

    __tablename__ = "dashboard_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    aquarium_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aquariums.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(60), nullable=False)
    type: Mapped[DashboardCardType] = mapped_column(Enum(DashboardCardType, validate_strings=True), nullable=False)
    icon: Mapped[str] = mapped_column(String(40), nullable=False, default="sensors")
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    col_span: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    # Ordre d'affichage : rempli automatiquement à la création (append en fin de grille).
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Selon le type de carte : sensor_id seul (temperature/water_param/
    # binary_level), sensor_high_id+sensor_low_id+equipment_id (ro_reserve),
    # ou equipment_id seul (osmolator_events, doit être un osmolateur).
    # Pas de contrainte NOT NULL/FK stricte ici : la validation "bon champ
    # pour le bon type" se fait côté schéma/route, pas au niveau SQL.
    sensor_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("sensors.id", ondelete="SET NULL"), nullable=True)
    sensor_high_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("sensors.id", ondelete="SET NULL"), nullable=True)
    sensor_low_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("sensors.id", ondelete="SET NULL"), nullable=True)
    equipment_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("equipments.id", ondelete="SET NULL"), nullable=True)
    # Alternative à sensor_id pour une carte water_param : paramètre saisi
    # manuellement (pas de capteur physique). L'un ou l'autre est renseigné,
    # jamais les deux.
    water_parameter_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("water_parameters.id", ondelete="SET NULL"), nullable=True
    )

    # Carte équipement à plusieurs lignes : identifiants dans l'ordre d'affichage
    # (equipment_id reste utilisé pour une carte à un seul équipement)
    equipment_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # Période de la courbe (24h, 7d, 30d, 90d) ; vide = défaut selon la source
    period: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    # Carte de niveau : état considéré comme normal (HIGH / LOW), vide = haut
    normal_state: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)

    target_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)

    aquarium: Mapped["Aquarium"] = relationship(back_populates="dashboard_cards")
