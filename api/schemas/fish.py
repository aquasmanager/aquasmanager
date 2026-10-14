from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class FishBase(BaseModel):
    aquarium_id: int = Field(gt=0, description="ID de l'aquarium")
    name: str = Field(min_length=4, description="Nom du poisson", examples=["Euphyllia paraancora"])
    quantity: int = Field(default=1, ge=1, le=9999, description="Nombre d'individus")
    date_acquisition: date = Field(description="Date d'achat", examples=["2025-12-25"])
    scientific_name: str = Field(min_length=4, description="Nom scientifique", examples=["Euphyllia"])
    family: str = Field(min_length=4, description="Famille du poisson", examples=["Caryophylliidae"])
    origin: str = Field(min_length=4, description="Origine du poisson", examples=["Mariculture"])
    max_height: int = Field(gt=0, description="Taille maximum du poisson")
    min_volume: int = Field(gt=0, description="Volume minimum de l'aquarium")
    reef_safe: bool = Field(description="Est-ce que le poisson est compatible avec les coraux")


class FishCreate(FishBase):
    pass


class FishRead(FishBase):
    id: int = Field(gt=0, description="ID du poisson (auto généré)")

    model_config = ConfigDict(from_attributes=True)


class FishListResponse(BaseModel):
    total: int
    fishes: List[FishRead]


class FishUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=4, description="Nom du poisson", examples=["Euphyllia"])
    quantity: Optional[int] = Field(default=None, ge=1, le=9999)
    date_acquisition: Optional[date] = Field(None, description="Date d'achat", examples=["2025-12-25"])
    scientific_name: Optional[str] = Field(None, min_length=4, description="Nom scientifique", examples=["Euphyllia"])
    family: Optional[str] = Field(None, min_length=4, description="Famille du poisson", examples=["Caryophylliidae"])
    origin: Optional[str] = Field(None, min_length=4, description="Origine du poisson", examples=["Mariculture"])
    max_height: Optional[int] = Field(None, gt=0, description="Taille maximum du poisson")
    min_volume: Optional[int] = Field(None, gt=0, description="Volume minimum de l'aquarium")
    reef_safe: Optional[bool] = Field(None, description="Est-ce que le poisson est compatible avec les coraux")

    model_config = ConfigDict(from_attributes=True)
