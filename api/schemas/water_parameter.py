from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class WaterParameterReadingBase(BaseModel):
    value: float
    timestamp: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=200)
    icp_batch_id: Optional[int] = None


class WaterParameterReadingCreate(WaterParameterReadingBase):
    pass


class WaterParameterReadingUpdate(BaseModel):
    value: Optional[float] = None
    timestamp: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=200)


class WaterParameterBatchValue(BaseModel):
    water_parameter_id: int
    value: float


class WaterParameterReadingBatchCreate(BaseModel):
    """Saisie de plusieurs paramètres d'un coup (même date, même note)."""

    aquarium_id: int = Field(gt=0)
    timestamp: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=200)
    values: list[WaterParameterBatchValue] = Field(min_length=1, max_length=100)


class WaterParameterReadingRead(BaseModel):
    id: int
    water_parameter_id: int
    value: float
    timestamp: datetime
    note: Optional[str] = None
    icp_batch_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class WaterParameterBase(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    unit: Optional[str] = Field(default=None, max_length=20)
    target_min: Optional[float] = None
    target_max: Optional[float] = None
    pinned: bool = False


class WaterParameterCreate(WaterParameterBase):
    aquarium_id: int = Field(gt=0)


class WaterParameterUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=30)
    unit: Optional[str] = Field(default=None, max_length=20)
    target_min: Optional[float] = None
    target_max: Optional[float] = None
    pinned: Optional[bool] = None


class WaterParameterRead(WaterParameterBase):
    id: int
    aquarium_id: int
    last_value: Optional[float] = None
    last_reading_at: Optional[datetime] = None
    full_name: Optional[str] = Field(default=None, description="Nom complet (ex: Calcium pour Ca)")
    in_target: Optional[bool] = Field(default=None, description="Dernière valeur dans la cible (null si pas de relevé ou de cible)")

    model_config = ConfigDict(from_attributes=True)


class TargetDefaultRead(BaseModel):
    name: str
    full_name: Optional[str] = None
    unit: str
    target_min: float
    target_max: float


class ApplyDefaultTargetsResult(BaseModel):
    updated: list[str]
    parameters: list[WaterParameterRead]


class IcpImportRow(BaseModel):
    name: str
    label: str
    value: float
    unit: Optional[str] = None
    target: Optional[float] = None
    status: Optional[str] = None


class IcpImportBatchCreate(BaseModel):
    aquarium_id: int = Field(gt=0)
    lab: str = Field(min_length=1, max_length=30)
    sample_date: datetime


class IcpImportBatchRead(BaseModel):
    id: int
    aquarium_id: int
    lab: str
    sample_date: datetime
    created_at: datetime
    pdf_filename: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class IcpBatchReadingRead(BaseModel):
    water_parameter_id: int
    name: str
    unit: Optional[str] = None
    value: float

    model_config = ConfigDict(from_attributes=True)
