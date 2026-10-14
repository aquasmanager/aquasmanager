from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ParameterShareCreate(BaseModel):
    aquarium_id: int = Field(gt=0)
    label: Optional[str] = Field(default=None, max_length=80)
    # 0 = dernières valeurs seulement
    history_days: Literal[0, 7, 30, 90] = 30
    pinned_only: bool = False
    # None = sans expiration
    expires_in_days: Optional[int] = Field(default=7, ge=1, le=365)


class ParameterShareRead(BaseModel):
    id: int
    token: str
    aquarium_id: int
    label: Optional[str] = None
    history_days: int
    pinned_only: bool
    expires_at: Optional[datetime] = None
    view_count: int
    last_viewed_at: Optional[datetime] = None
    created_at: datetime
    # active / expired
    state: str

    model_config = ConfigDict(from_attributes=True)


class SharedPoint(BaseModel):
    timestamp: datetime
    value: float


class SharedParameter(BaseModel):
    name: str
    full_name: Optional[str] = None
    unit: Optional[str] = None
    target_min: Optional[float] = None
    target_max: Optional[float] = None
    last_value: Optional[float] = None
    last_reading_at: Optional[datetime] = None
    in_target: Optional[bool] = None
    history: list[SharedPoint] = []


class SharedAquarium(BaseModel):
    name: str
    volume: int
    water_type: str
    biotope: str


class PublicParameters(BaseModel):
    aquarium: SharedAquarium
    history_days: int
    expires_at: Optional[datetime] = None
    generated_at: datetime
    parameters: list[SharedParameter]
