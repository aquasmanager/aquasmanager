from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from models.aquarium import AquariumWaterType
from models.coral import CoralType
from models.plant import PlantGrowing, PlantLocation
from models.species import InvertebrateCategory


def _check_link(value: Optional[str]) -> Optional[str]:
    # Affiché comme lien cliquable : seules les URL web sont acceptées (pas de javascript:)
    if value is None or not value.strip():
        return None
    value = value.strip()
    if not value.lower().startswith(("http://", "https://")):
        raise ValueError("Le lien doit commencer par http:// ou https://")
    return value


class _LinkValidated(BaseModel):
    @field_validator("link", check_fields=False)
    @classmethod
    def validate_link(cls, value: Optional[str]) -> Optional[str]:
        return _check_link(value)


class FishSpeciesBase(_LinkValidated):
    common_name: str = Field(min_length=1, max_length=30)
    scientific_name: str = Field(min_length=1, max_length=30)
    water_type: AquariumWaterType = AquariumWaterType.sea
    family: Optional[str] = Field(default=None, max_length=30)
    origin: Optional[str] = Field(default=None, max_length=30)
    max_height: int = Field(gt=0, description="Taille adulte (cm)")
    min_volume: int = Field(gt=0, description="Volume minimal conseillé (L)")
    reef_safe: bool = True
    notes: Optional[str] = None
    link: Optional[str] = Field(default=None, max_length=300, description="Fiche de référence (Fishipedia, revendeur...)")


class FishSpeciesUpdate(_LinkValidated):
    common_name: Optional[str] = Field(default=None, min_length=1, max_length=30)
    scientific_name: Optional[str] = Field(default=None, min_length=1, max_length=30)
    water_type: Optional[AquariumWaterType] = None
    family: Optional[str] = Field(default=None, max_length=30)
    origin: Optional[str] = Field(default=None, max_length=30)
    max_height: Optional[int] = Field(default=None, gt=0)
    min_volume: Optional[int] = Field(default=None, gt=0)
    reef_safe: Optional[bool] = None
    notes: Optional[str] = None
    link: Optional[str] = Field(default=None, max_length=300)


class FishSpeciesRead(FishSpeciesBase):
    id: int
    builtin: bool
    customized: bool = False
    warnings: list[str] = Field(default_factory=list, description="Avertissements pour l'aquarium demandé")

    model_config = ConfigDict(from_attributes=True)


class CoralSpeciesBase(_LinkValidated):
    common_name: str = Field(min_length=1, max_length=30)
    scientific_name: str = Field(min_length=1, max_length=30)
    type: CoralType
    family: Optional[str] = Field(default=None, max_length=30)
    origin: Optional[str] = Field(default=None, max_length=30)
    light_min: int = Field(ge=1, le=15, description="Lumière min (1 = 50 PAR, 15 = 750 PAR)")
    light_max: int = Field(ge=1, le=15)
    brewing_min: int = Field(ge=1, le=10)
    brewing_max: int = Field(ge=1, le=10)
    aggressiveness_level: int = Field(ge=1, le=10)
    resistance_level: int = Field(ge=1, le=10, description="10 = très robuste")
    location_level: int = Field(ge=1, le=10, description="1 = fond, 10 = haut du bac")
    notes: Optional[str] = None
    link: Optional[str] = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def check_ranges(self):
        if self.light_min > self.light_max or self.brewing_min > self.brewing_max:
            raise ValueError("Le minimum doit être inférieur ou égal au maximum.")
        return self


class CoralSpeciesUpdate(_LinkValidated):
    common_name: Optional[str] = Field(default=None, min_length=1, max_length=30)
    scientific_name: Optional[str] = Field(default=None, min_length=1, max_length=30)
    type: Optional[CoralType] = None
    family: Optional[str] = Field(default=None, max_length=30)
    origin: Optional[str] = Field(default=None, max_length=30)
    light_min: Optional[int] = Field(default=None, ge=1, le=15)
    light_max: Optional[int] = Field(default=None, ge=1, le=15)
    brewing_min: Optional[int] = Field(default=None, ge=1, le=10)
    brewing_max: Optional[int] = Field(default=None, ge=1, le=10)
    aggressiveness_level: Optional[int] = Field(default=None, ge=1, le=10)
    resistance_level: Optional[int] = Field(default=None, ge=1, le=10)
    location_level: Optional[int] = Field(default=None, ge=1, le=10)
    notes: Optional[str] = None
    link: Optional[str] = Field(default=None, max_length=300)


class CoralSpeciesRead(CoralSpeciesBase):
    id: int
    builtin: bool
    customized: bool = False
    warnings: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PlantSpeciesBase(_LinkValidated):
    common_name: str = Field(min_length=1, max_length=30)
    scientific_name: str = Field(min_length=1, max_length=30)
    family: Optional[str] = Field(default=None, max_length=30)
    origin: Optional[str] = Field(default=None, max_length=30)
    light_min: int = Field(ge=1, le=10)
    light_max: int = Field(ge=1, le=10)
    temperature_min: int = Field(ge=10, le=35, description="°C")
    temperature_max: int = Field(ge=10, le=35, description="°C")
    growing: PlantGrowing
    resistance_level: int = Field(ge=1, le=10)
    max_height: int = Field(ge=1, le=50, description="cm")
    location: PlantLocation
    notes: Optional[str] = None
    link: Optional[str] = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def check_ranges(self):
        if self.light_min > self.light_max or self.temperature_min > self.temperature_max:
            raise ValueError("Le minimum doit être inférieur ou égal au maximum.")
        return self


class PlantSpeciesUpdate(_LinkValidated):
    common_name: Optional[str] = Field(default=None, min_length=1, max_length=30)
    scientific_name: Optional[str] = Field(default=None, min_length=1, max_length=30)
    family: Optional[str] = Field(default=None, max_length=30)
    origin: Optional[str] = Field(default=None, max_length=30)
    light_min: Optional[int] = Field(default=None, ge=1, le=10)
    light_max: Optional[int] = Field(default=None, ge=1, le=10)
    temperature_min: Optional[int] = Field(default=None, ge=10, le=35)
    temperature_max: Optional[int] = Field(default=None, ge=10, le=35)
    growing: Optional[PlantGrowing] = None
    resistance_level: Optional[int] = Field(default=None, ge=1, le=10)
    max_height: Optional[int] = Field(default=None, ge=1, le=50)
    location: Optional[PlantLocation] = None
    notes: Optional[str] = None
    link: Optional[str] = Field(default=None, max_length=300)


class PlantSpeciesRead(PlantSpeciesBase):
    id: int
    builtin: bool
    customized: bool = False
    warnings: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class InvertebrateSpeciesBase(_LinkValidated):
    common_name: str = Field(min_length=1, max_length=30)
    scientific_name: str = Field(min_length=1, max_length=30)
    water_type: AquariumWaterType
    category: InvertebrateCategory
    family: Optional[str] = Field(default=None, max_length=30)
    origin: Optional[str] = Field(default=None, max_length=30)
    min_volume: int = Field(gt=0, description="Volume minimal conseillé (L)")
    reef_safe: bool = True
    notes: Optional[str] = None
    link: Optional[str] = Field(default=None, max_length=300)


class InvertebrateSpeciesUpdate(_LinkValidated):
    common_name: Optional[str] = Field(default=None, min_length=1, max_length=30)
    scientific_name: Optional[str] = Field(default=None, min_length=1, max_length=30)
    water_type: Optional[AquariumWaterType] = None
    category: Optional[InvertebrateCategory] = None
    family: Optional[str] = Field(default=None, max_length=30)
    origin: Optional[str] = Field(default=None, max_length=30)
    min_volume: Optional[int] = Field(default=None, gt=0)
    reef_safe: Optional[bool] = None
    notes: Optional[str] = None
    link: Optional[str] = Field(default=None, max_length=300)


class InvertebrateSpeciesRead(InvertebrateSpeciesBase):
    id: int
    builtin: bool
    customized: bool = False
    warnings: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
