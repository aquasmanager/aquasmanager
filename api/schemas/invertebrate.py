from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class InvertebrateBase(BaseModel):
    aquarium_id: int = Field(gt=0, description="ID de l'aquarium")
    name: str = Field(min_length=4, description="Nom de l'invertébré", examples=["Crevette nettoyeuse"])
    quantity: int = Field(default=1, ge=1, le=9999, description="Nombre d'individus")
    date_acquisition: date = Field(description="Date d'achat", examples=["2025-12-25"])
    scientific_name: str = Field(min_length=4, description="Nom scientifique", examples=["Lysmata amboinensis"])
    family: str = Field(min_length=4, description="Famille", examples=["Lysmatidae"])
    origin: str = Field(min_length=4, description="Origine", examples=["Elevage"])


class InvertebrateCreate(InvertebrateBase):
    pass


class InvertebrateRead(InvertebrateBase):
    id: int = Field(gt=0, description="ID de l'invertébré (auto généré)")

    model_config = ConfigDict(from_attributes=True)


class InvertebrateListResponse(BaseModel):
    total: int
    invertebrates: List[InvertebrateRead]


class InvertebrateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=4, description="Nom de l'invertébré")
    quantity: Optional[int] = Field(default=None, ge=1, le=9999)
    date_acquisition: Optional[date] = Field(None, description="Date d'achat", examples=["2025-12-25"])
    scientific_name: Optional[str] = Field(None, min_length=4, description="Nom scientifique")
    family: Optional[str] = Field(None, min_length=4, description="Famille")
    origin: Optional[str] = Field(None, min_length=4, description="Origine", examples=["Mariculture"])

    model_config = ConfigDict(from_attributes=True)
