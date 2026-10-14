from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Brand = Literal["reolink", "tapo", "rtsp"]
Quality = Literal["main", "sub"]


class CameraBase(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    brand: Brand = "rtsp"
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=554, ge=1, le=65535)
    username: str = Field(default="", max_length=100)
    main_path: str = Field(default="", max_length=255)
    sub_path: str = Field(default="", max_length=255)
    sort_order: int = 0


class CameraCreate(CameraBase):
    aquarium_id: int
    password: str = Field(default="", max_length=200)


class CameraUpdate(CameraBase):
    # Vide : mot de passe inchangé ; clear_password pour le retirer
    password: str = Field(default="", max_length=200)
    clear_password: bool = False


class CameraRead(CameraBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    aquarium_id: int
    has_password: bool
    created_at: datetime


class CameraTest(BaseModel):
    """Réglages à tester ; camera_id pour reprendre le mot de passe enregistré."""

    camera_id: int | None = None
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=554, ge=1, le=65535)
    username: str = Field(default="", max_length=100)
    password: str = Field(default="", max_length=200)
    path: str = Field(default="", max_length=255)


class CameraStatus(BaseModel):
    enabled: bool
    presets: dict[str, dict[str, str]]
