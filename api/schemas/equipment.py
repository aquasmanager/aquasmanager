from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PhysicalContact(str, Enum):
    NC = "NC"
    NO = "NO"


class EquipmentStatus(str, Enum):
    ON = "ON"
    OFF = "OFF"


class EquipmentMode(str, Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"


class EquipmentCategory(str, Enum):
    OSMOLATOR = "OSMOLATOR"
    OSMOSEUR = "OSMOSEUR"
    PUMP = "PUMP"
    BRASSAGE = "BRASSAGE"
    ECUMOR = "ECUMOR"
    COOLER = "COOLER"
    HEATER = "HEATER"
    LIGHT = "LIGHT"
    OTHER = "OTHER"


class EquipmentBase(BaseModel):
    name: str
    technical_name: str
    aquarium_id: int
    controller_id: int
    pin_id: int
    inverted: bool
    physical_contact: PhysicalContact
    status: EquipmentStatus
    mode: EquipmentMode
    restart_delay: int = 0
    category: EquipmentCategory = EquipmentCategory.OTHER
    max_duration_seconds: Optional[int] = Field(
        default=None, ge=5, le=3600, description="Coupure de sécurité (s) des osmolateurs, 45 s si vide"
    )


class EquipmentCreate(BaseModel):
    name: str
    aquarium_id: int
    controller_id: int
    pin_id: int
    physical_contact: PhysicalContact
    status: EquipmentStatus
    mode: EquipmentMode
    # Vide : déduit du type de contact (NC = logique inversée)
    inverted: Optional[bool] = None
    restart_delay: int = 0
    category: EquipmentCategory = EquipmentCategory.OTHER
    max_duration_seconds: Optional[int] = Field(default=None, ge=5, le=3600)


class EquipmentUpdate(EquipmentBase):
    name: Optional[str] = None
    technical_name: Optional[str] = None
    aquarium_id: Optional[int] = None
    controller_id: Optional[int] = None
    pin_id: Optional[int] = None
    inverted: Optional[bool] = None
    physical_contact: Optional[PhysicalContact] = None
    status: Optional[EquipmentStatus] = None
    mode: Optional[EquipmentMode] = None
    restart_delay: Optional[int] = None
    category: Optional[EquipmentCategory] = None
    max_duration_seconds: Optional[int] = Field(default=None, ge=5, le=3600)
    created_at: Optional[datetime] = None


class EquipmentRead(EquipmentBase):
    id: int

    pin_number: Optional[str] = None
    # Broche d'un module d'extension (PCF8574...) plutôt qu'une GPIO de l'ESP
    module_id: Optional[int] = None
    module_number: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class EquipmentModeUpdate(BaseModel):
    mode: EquipmentMode = Field(..., description="Le nouveau mode de l'équipement")


class EquipmentListResponse(BaseModel):
    total: int
    equipments: List[EquipmentRead]


class EquipmentStatusUpdate(BaseModel):
    status: str  # "ON" ou "OFF"

