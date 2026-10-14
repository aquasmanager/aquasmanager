from enum import Enum
from pydantic import BaseModel, ConfigDict
from typing import Optional, List

class Bus(str, Enum):
    GPIO = "GPIO"
    PMW = "PMW"
    I2C = "I2C"
    SPI = "SPI"
    ONEWIRE = "1WIRE"
    ADC = "ADC"
    UART = "UART"
    FREE = "FREE"

class Mode(str, Enum):
    IN = "IN"
    OUT = "OUT"
    SENSOR = "SENSOR"
    FREE = "FREE"

class ControllerPinBase(BaseModel):
    controller_id: int
    pin_number: int
    bus: Bus
    mode: Mode
    label: Optional[str]

class ControllerPinCreate(ControllerPinBase):
    pass


class ControllerPinUpdate(ControllerPinBase):
    controller_id: Optional[int] = None
    pin_number: Optional[int] = None
    bus: Optional[Bus] = None
    mode: Optional[Mode] = None
    label: Optional[str] = None


class ControllerPinRead(ControllerPinBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

class ControllerPinListResponse(BaseModel):
    total: int
    controllers: List[ControllerPinRead]