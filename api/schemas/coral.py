from datetime import date
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class Type(str, Enum):
    SPS = "SPS"
    LPS = "LPS"
    MOU = "MOU"


class Range(BaseModel):
    min: int = Field(ge=1, le=10, description="Niveau minimal", examples=["0,1,2,...,10"])
    max: int = Field(ge=1, le=10, description="Niveau maximal", examples=["0,1,2,...,10"])


class LightRange(BaseModel):
    """Lumière d'un corail : 1 à 15, par paliers de 50 PAR (1 = 50 PAR, 15 = 750 PAR)."""

    min: int = Field(ge=1, le=15, description="Niveau minimal (× 50 PAR)")
    max: int = Field(ge=1, le=15, description="Niveau maximal (× 50 PAR)")


class CoralBase(BaseModel):
    aquarium_id: int = Field(gt=0, description="ID de l'aquarium")
    name: str = Field(min_length=4, description="Nom du corail", examples=["Euphyllia paraancora"])
    quantity: int = Field(default=1, ge=1, le=9999, description="Nombre d'individus")
    # Facultatif : beaucoup de boutures (maricultures, échanges) n'ont pas de numéro CITES
    cites: str = Field(default="", max_length=30, description="Numéro de cites", examples=["Numéro_cites"])
    type: Type = Field(pattern="^(SPS|LPS|MOU)$", description="Type du corail", examples=["SPS | LPS | MOU"])
    scientific_name: str = Field(min_length=4, description="Nom scientifique", examples=["Euphyllia"])
    family: str = Field(min_length=4, description="Famille du corail", examples=["Caryophylliidae"])
    origin: str = Field(min_length=4, description="Origine du corail", examples=["Mariculture"])
    acquired_from: Optional[str] = Field(default=None, max_length=120, description="Provenance : acquis auprès de (magasin, bourse, particulier)")
    light_range: Optional[LightRange] = Field(description="Niveau de lumière (1 = 50 PAR)", examples=["{min:6, max:12}"])
    brewing_range: Optional[Range] = Field(description="Niveau de brassage", examples=["{min:2, max:5}"])
    aggressiveness_level: int = Field(ge=1, le=10, description="Niveau d'agréssivité", examples=["0,1,2,...,10"])
    resistance_level: int = Field(ge=1, le=10, description="Niveau de résistance", examples=["0,1,2,...,10"])
    location_level: int = Field(ge=1, le=10, description="Hauteur dans l'aquarium", examples=["0,1,2,...,10"])
    date_acquisition: date = Field(description="Date d'achat", examples=["2025-12-25"])


class CoralCreate(CoralBase):
    pass


class CoralRead(CoralBase):
    id: int = Field(gt=0, description="ID du corail (auto généré)")

    model_config = ConfigDict(from_attributes=True)

class CoralListResponse(BaseModel):
    total: int
    corals: List[CoralRead]


class CoralUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=4, description="Nom du corail", examples=["Euphyllia"])
    quantity: Optional[int] = Field(default=None, ge=1, le=9999)
    cites: Optional[str] = Field(None, max_length=30, description="Cites", examples=["FR2066HY9999"])
    type: Optional[Type] = Field(
        None, pattern="^(SPS|LPS|MOU)$", description="Type du corail", examples=["SPS | LPS | MOU"]
    )
    scientific_name: Optional[str] = Field(None, min_length=4, description="Nom scientifique", examples=["Euphyllia"])
    family: Optional[str] = Field(None, min_length=4, description="Famille du corail", examples=["Caryophylliidae"])
    origin: Optional[str] = Field(None, min_length=4, description="Origine du corail", examples=["Mariculture"])
    acquired_from: Optional[str] = Field(default=None, max_length=120, description="Provenance : acquis auprès de (magasin, bourse, particulier)")
    light_range: Optional[LightRange] = Field(None, description="Niveau de lumière (1 = 50 PAR)", examples=["{min:6, max:12}"])
    brewing_range: Optional[Range] = Field(None, description="Niveau de brassage", examples=["{min:2, max:5}"])
    aggressiveness_level: Optional[int] = Field(
        None, ge=1, le=10, description="Niveau d'agréssivité", examples=["0,1,2,...,10"]
    )
    resistance_level: Optional[int] = Field(
        None, ge=1, le=10, description="Niveau de résistance", examples=["0,1,2,...,10"]
    )
    location_level: Optional[int] = Field(
        None, ge=1, le=10, description="Hauteur dans l'aquarium", examples=["0,1,2,...,10"]
    )
    date_acquisition: Optional[date] = Field(None, description="Date d'achat", examples=["2025-12-25"])

    model_config = ConfigDict(from_attributes=True)