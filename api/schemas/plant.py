from datetime import date
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class Growing(str, Enum):
    slow = "slow"
    average = "average"
    fast = "fast"


class Location(str, Enum):
    front = "front"
    middle = "middle"
    back = "back"


class Range(BaseModel):
    min: int = Field(ge=1, le=35, description="Niveau minimal", examples=["0,1,2,...,10"])
    max: int = Field(ge=1, le=35, description="Niveau maximal", examples=["0,1,2,...,10"])


class PlantBase(BaseModel):
    aquarium_id: int = Field(gt=0, description="ID de l'aquarium")
    name: str = Field(min_length=4, description="Nom de la plante", examples=["Anubia Nana"])
    quantity: int = Field(default=1, ge=1, le=9999, description="Nombre d'individus")
    scientific_name: str = Field(min_length=4, description="Nom scientifique", examples=["Anubia"])
    family: str = Field(min_length=4, description="Famille de la plante", examples=["Aracea"])
    origin: str = Field(min_length=4, description="Origine de la plante", examples=["Afrique"])
    light_range: Range = Field(description="Niveau de lumière", examples=["{min:3, max:6}"])
    temperature_range: Range = Field(description="Température (C°)", examples=["{min:15, max:26}"])
    growing: Growing = Field(
        pattern="^(slow|average|fast)$", description="Croissance de la plante", examples=["slow | average | fast"]
    )
    resistance_level: int = Field(ge=1, le=10, description="Niveau de résistance", examples=["0,1,2,...,10"])
    max_height: int = Field(ge=1, le=50, description="Hauteur de la plante", examples=["0,1,2,...,50"])
    location: Location = Field(
        pattern="^(front|middle|back)$", description="Emplacement de la plante", examples=["front | middle | back"]
    )
    date_acquisition: date = Field(description="Date d'achat", examples=["2025-12-25"])


class PlantCreate(PlantBase):
    pass


class PlantRead(PlantBase):
    id: int = Field(gt=0, description="ID de la plante (auto généré)")

    model_config = ConfigDict(from_attributes=True)


class PlantListResponse(BaseModel):
    total: int
    plants: List[PlantRead]


class PlantUpdate(BaseModel):
    name: str = Field(None, min_length=4, description="Nom de la plante", examples=["Anubia Nana"])
    quantity: Optional[int] = Field(default=None, ge=1, le=9999)
    scientific_name: str = Field(None, min_length=4, description="Nom scientifique", examples=["Anubia"])
    family: str = Field(None, min_length=4, description="Famille de la plante", examples=["Aracea"])
    origin: str = Field(None, min_length=4, description="Origine de la plante", examples=["Afrique"])
    light_range: Range = Field(None, description="Niveau de lumière", examples=["{min:3, max:6}"])
    temperature_range: Range = Field(None, description="Température (C°)", examples=["{min:15, max:26}"])
    growing: Growing = Field(
        None, pattern="^(slow|average|fast)$", description="Croissance de la plante", examples=["slow | average | fast"]
    )
    resistance_level: int = Field(None, ge=1, le=10, description="Niveau de résistance", examples=["0,1,2,...,10"])
    max_height: int = Field(None, ge=1, le=50, description="Hauteur de la plante", examples=["0,1,2,...,50"])
    location: Location = Field(
        None,
        pattern="^(front|middle|back)$",
        description="Emplacement de la plante",
        examples=["front | middle | back"],
    )
    date_acquisition: date = Field(None, description="Date d'achat", examples=["2025-12-25"])

    model_config = ConfigDict(from_attributes=True)