from typing import Optional

from pydantic import BaseModel, Field, field_validator
import re

from models.io_module import ModuleType


def _i2c_address(v: str) -> str:
    # Accepte 0x20, 0X20, 0x3F... ; normalisé en minuscules (0x20)
    if not re.match(r'^0[xX][0-9a-fA-F]{2}$', v.strip()):
        raise ValueError("L'adresse doit être au format hexadécimal (ex: 0x20)")
    return v.strip().lower()


class ModuleCreate(BaseModel):
    address: str = Field(description="Adresse I2C du module", examples=["0x20"])
    type: ModuleType = Field(description="Modèle du module (PCF8574 ou PCF8575)")
    # Numéro affiché (« Module 1 ») ; vide = premier numéro libre du contrôleur
    number: Optional[int] = Field(default=None, ge=1, le=99)

    @field_validator('address')
    @classmethod
    def validate_i2c_address(cls, v: str) -> str:
        return _i2c_address(v)


class ModuleUpdate(BaseModel):
    address: Optional[str] = None
    type: Optional[ModuleType] = None
    number: Optional[int] = Field(default=None, ge=1, le=99)

    @field_validator('address')
    @classmethod
    def validate_i2c_address(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _i2c_address(v)

