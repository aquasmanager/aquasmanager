from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class Type(str, Enum):
    RPI = "RPI"
    ESP32 = "ESP32"
    ESP8266 = "ESP8266"
    ARDUINO = "ARDUINO"


class Status(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    INITIALIZING = "INITIALIZING"
    FLASHING = "FLASHING"
    FLASH_FAILED = "FLASH_FAILED"


# ----------------------------------------------------------------------
# 1. SCHÉMA DE BASE
# ----------------------------------------------------------------------

class ControllerBase(BaseModel):
    name: str = Field(..., max_length=30)
    technical_name: str
    type: Type
    zone: str = Field(..., max_length=30)
    ip: Optional[str] = None  # Optionnel pour autoriser l'auto-attribution


# ----------------------------------------------------------------------
# 2. CRÉATION (Input POST)
# ----------------------------------------------------------------------

class ControllerCreate(BaseModel):
    name: str
    type: Type
    zone: str
    ip: Optional[str] = None  # Optionnel : si None -> auto-attribution, si fourni -> IP du scan


# ----------------------------------------------------------------------
# 3. MISE À JOUR (Input PATCH)
# ----------------------------------------------------------------------

RtcModel = Literal["DS3231", "DS1307", "PCF8563", "PCF85063"]


class ControllerUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=30)
    rtc_model: Optional[RtcModel] = Field(None, description="Horloge RTC sur pile, null = aucune")
    i2c_frequency_khz: Optional[Literal[10, 25, 50, 100, 400]] = Field(
        None, description="Fréquence du bus I2C (kHz) : 50 par défaut, 10 ou 25 pour un câble long"
    )
    type: Optional[Type] = None
    zone: Optional[str] = Field(None, max_length=30)
    ip: Optional[str] = None
    status: Optional[Status] = None
    is_dirty: Optional[bool] = None
    yaml_config: Optional[str] = None


# ----------------------------------------------------------------------
# 4. LECTURE (Output GET)
# ----------------------------------------------------------------------

class ControllerRead(ControllerBase):
    id: int
    status: Status = Status.OFFLINE
    is_dirty: bool = True
    last_sync: Optional[datetime] = None
    created_at: Optional[datetime] = None
    # Jamais renvoyé : contient les mots de passe Wi-Fi et MQTT (voir /controllers/{id}/config)
    yaml_config: Optional[str] = Field(default=None, exclude=True)
    rtc_model: Optional[str] = None
    i2c_frequency_khz: int = 50

    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------------------------------------
# 5. RÉPONSES ET CONFIGURATIONS DÉDIÉES
# ----------------------------------------------------------------------

class ControllerListResponse(BaseModel):
    total: int
    controllers: List[ControllerRead]