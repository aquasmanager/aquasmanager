"""
species.py

Catalogue d'espèces (poissons, coraux, plantes, invertébrés) servant à
pré-remplir les fiches.
builtin = espèce du catalogue commun : jeu de départ (services/species_catalog.py)
puis catalogue en ligne (services/catalog_sync.py), qui met à jour les fiches
builtin tant que l'utilisateur ne les a pas modifiées (customized).
Supprimer une espèce builtin la masque (hidden) : sinon le catalogue la
réinsérerait au démarrage suivant.
"""

import enum
from typing import Optional

from sqlalchemy import Boolean, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from middleware.database import Base
from models.aquarium import AquariumWaterType
from models.coral import CoralType
from models.plant import PlantGrowing, PlantLocation


class FishSpecies(Base):
    __tablename__ = "fish_species"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    common_name: Mapped[str] = mapped_column(String(30), nullable=False)
    scientific_name: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    water_type: Mapped[AquariumWaterType] = mapped_column(
        Enum(AquariumWaterType), nullable=False, default=AquariumWaterType.sea
    )
    family: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    origin: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    max_height: Mapped[int] = mapped_column(Integer, nullable=False)  # cm
    min_volume: Mapped[int] = mapped_column(Integer, nullable=False)  # litres
    reef_safe: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    link: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Fiche du catalogue commun modifiée ici : plus mise à jour par la synchronisation
    customized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CoralSpecies(Base):
    __tablename__ = "coral_species"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    common_name: Mapped[str] = mapped_column(String(30), nullable=False)
    scientific_name: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    type: Mapped[CoralType] = mapped_column(Enum(CoralType, validate_strings=True), nullable=False)
    family: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    origin: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    # Mêmes échelles que Coral : 1-10, sauf la lumière 1-15 (1 = 50 PAR)
    light_min: Mapped[int] = mapped_column(Integer, nullable=False)
    light_max: Mapped[int] = mapped_column(Integer, nullable=False)
    brewing_min: Mapped[int] = mapped_column(Integer, nullable=False)
    brewing_max: Mapped[int] = mapped_column(Integer, nullable=False)
    aggressiveness_level: Mapped[int] = mapped_column(Integer, nullable=False)
    resistance_level: Mapped[int] = mapped_column(Integer, nullable=False)
    location_level: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    link: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Fiche du catalogue commun modifiée ici : plus mise à jour par la synchronisation
    customized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PlantSpecies(Base):
    __tablename__ = "plant_species"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    common_name: Mapped[str] = mapped_column(String(30), nullable=False)
    scientific_name: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    family: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    origin: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    # Mêmes échelles que Plant : lumière 1-10, température °C, hauteur en cm
    light_min: Mapped[int] = mapped_column(Integer, nullable=False)
    light_max: Mapped[int] = mapped_column(Integer, nullable=False)
    temperature_min: Mapped[int] = mapped_column(Integer, nullable=False)
    temperature_max: Mapped[int] = mapped_column(Integer, nullable=False)
    growing: Mapped[PlantGrowing] = mapped_column(Enum(PlantGrowing), nullable=False)
    resistance_level: Mapped[int] = mapped_column(Integer, nullable=False)
    max_height: Mapped[int] = mapped_column(Integer, nullable=False)
    location: Mapped[PlantLocation] = mapped_column(Enum(PlantLocation), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    link: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Fiche du catalogue commun modifiée ici : plus mise à jour par la synchronisation
    customized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class InvertebrateCategory(enum.Enum):
    shrimp = "shrimp"
    crab = "crab"
    snail = "snail"
    clam = "clam"
    starfish = "starfish"
    urchin = "urchin"
    anemone = "anemone"
    other = "other"


class InvertebrateSpecies(Base):
    __tablename__ = "invertebrate_species"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    common_name: Mapped[str] = mapped_column(String(30), nullable=False)
    scientific_name: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    water_type: Mapped[AquariumWaterType] = mapped_column(Enum(AquariumWaterType), nullable=False)
    category: Mapped[InvertebrateCategory] = mapped_column(Enum(InvertebrateCategory), nullable=False)
    family: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    origin: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    min_volume: Mapped[int] = mapped_column(Integer, nullable=False)  # litres
    # Eau de mer : sans danger pour les coraux (sans objet en eau douce)
    reef_safe: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    link: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Fiche du catalogue commun modifiée ici : plus mise à jour par la synchronisation
    customized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
