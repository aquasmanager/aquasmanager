from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict

from models.dashboard_card import DashboardCardType

Period = Literal["24h", "7d", "30d", "90d"]
LevelState = Literal["HIGH", "LOW"]


class DashboardCardBase(BaseModel):
    title: str = Field(min_length=1, max_length=60)
    type: DashboardCardType
    icon: str = Field(default="sensors", max_length=40)
    unit: Optional[str] = Field(default=None, max_length=20)
    col_span: int = Field(default=4, ge=1, le=12)

    sensor_id: Optional[int] = None
    sensor_high_id: Optional[int] = None
    sensor_low_id: Optional[int] = None
    equipment_id: Optional[int] = None
    # Carte équipement : plusieurs équipements (liste, dans l'ordre d'affichage)
    equipment_ids: Optional[list[int]] = Field(default=None, max_length=20)
    # Alternative à sensor_id pour une carte water_param saisie manuellement
    # (pas de capteur physique) : l'un ou l'autre est renseigné, jamais les deux.
    water_parameter_id: Optional[int] = None
    period: Optional[Period] = None
    normal_state: Optional[LevelState] = None

    target_min: Optional[float] = None
    target_max: Optional[float] = None


class DashboardCardCreate(DashboardCardBase):
    aquarium_id: int = Field(gt=0)


class DashboardCardUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=60)
    type: Optional[DashboardCardType] = None
    icon: Optional[str] = Field(default=None, max_length=40)
    unit: Optional[str] = Field(default=None, max_length=20)
    col_span: Optional[int] = Field(default=None, ge=1, le=12)
    position: Optional[int] = None

    sensor_id: Optional[int] = None
    sensor_high_id: Optional[int] = None
    sensor_low_id: Optional[int] = None
    equipment_id: Optional[int] = None
    equipment_ids: Optional[list[int]] = Field(default=None, max_length=20)
    water_parameter_id: Optional[int] = None
    period: Optional[Period] = None
    normal_state: Optional[LevelState] = None

    target_min: Optional[float] = None
    target_max: Optional[float] = None


class DashboardCardOrder(BaseModel):
    """Nouvel ordre des cartes d'un aquarium (identifiants dans l'ordre d'affichage)."""

    aquarium_id: int = Field(gt=0)
    ids: list[int]


class DashboardCardRead(DashboardCardBase):
    id: int
    aquarium_id: int
    position: int

    model_config = ConfigDict(from_attributes=True)
