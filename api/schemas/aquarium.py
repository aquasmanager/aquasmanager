from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class Type(str, Enum):
    sea = "sea"
    pure = "pure"


class AquariumBase(BaseModel):
    name: str = Field(min_length=4, description="Nom de l'auaquarium", examples=["Récifal"])
    volume: int = Field(gt=0, description="Volume de l'aquarium (L)", examples=["1000"])
    water_type: Type = Field(pattern="^(sea|pure)$", description="Type de l'eau", examples=["sea | pure"])
    biotope: str = Field(min_length=4, description="Biotope de l'auaquarium", examples=["Amazonien"])
    date_creation: date = Field(description="Date de mise en route", examples=["2025-12-25"])


class AquariumCreate(AquariumBase):
    pass


class AquariumRead(AquariumBase):
    id: int = Field(gt=0, description="ID de l'aquarium (auto généré)")
    # Fin prévue du mode maintenance en cours (None = pas de maintenance)
    maintenance_until: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AquariumListResponse(BaseModel):
    total: int
    aquariums: List[AquariumRead]


class AquariumUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=4, description="Nom de l'auaquarium", examples=["Récifal"])
    volume: Optional[int] = Field(None, gt=0, description="Volume de l'aquarium (L)", examples=["1000"])
    water_type: Optional[Type] = Field(
        None, pattern="^(sea|pure)$", description="Type de l'eau", examples=["sea | pure"]
    )
    biotope: Optional[str] = Field(None, min_length=4, description="Biotope de l'auaquarium", examples=["Amazonien"])
    date_creation: Optional[date] = Field(None, description="Date de mise en route", examples=["2025-12-25"])

    model_config = ConfigDict(from_attributes=True)
