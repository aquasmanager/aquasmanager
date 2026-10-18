import re
from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.light_channel import ChannelMode

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class SchedulePoint(BaseModel):
    minute: int = Field(ge=0, lt=1440, description="Minutes depuis minuit")
    intensity: int = Field(ge=0, le=100, description="Intensité (%)")


class LightChannelBase(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    pin_id: int
    color: str = "#ffffff"
    spectrum: str = "other"
    max_intensity: int = Field(default=100, ge=0, le=100)
    # Seuil sous lequel le canal reste éteint (zone instable du driver)
    min_intensity: int = Field(default=0, ge=0, le=100)
    inverted: bool = False

    @field_validator("color")
    @classmethod
    def check_color(cls, value: str) -> str:
        if not _HEX_COLOR.match(value):
            raise ValueError("Couleur attendue au format #rrggbb")
        return value.lower()


class LightChannelCreate(LightChannelBase):
    pass


class LightChannelUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=30)
    pin_id: Optional[int] = None
    color: Optional[str] = None
    spectrum: Optional[str] = None
    max_intensity: Optional[int] = Field(default=None, ge=0, le=100)
    min_intensity: Optional[int] = Field(default=None, ge=0, le=100)
    inverted: Optional[bool] = None

    @field_validator("color")
    @classmethod
    def check_color(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not _HEX_COLOR.match(value):
            raise ValueError("Couleur attendue au format #rrggbb")
        return value.lower() if value else value


class LightChannelRead(BaseModel):
    id: int
    light_id: int
    name: str
    pin_id: int
    pin_number: Optional[str] = None
    color: str
    spectrum: str
    mode: ChannelMode
    max_intensity: int
    min_intensity: int = 0
    current_intensity: int
    inverted: bool
    moonlight_intensity: int = 0
    schedule: List[SchedulePoint] = Field(default_factory=list)


class LightBase(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    aquarium_id: int
    controller_id: int
    pwm_frequency: int = Field(default=1000, ge=100, le=40000)
    acclimation_start: Optional[date] = None
    acclimation_days: Optional[int] = Field(default=None, ge=1, le=365)
    acclimation_start_percent: int = Field(default=50, ge=5, le=100)


class MoonlightChannel(BaseModel):
    channel_id: int
    intensity: int = Field(ge=1, le=100, description="Intensité plancher la nuit (%)")


class LightCreate(LightBase):
    pass


class LightUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=30)
    aquarium_id: Optional[int] = None
    controller_id: Optional[int] = None
    pwm_frequency: Optional[int] = Field(default=None, ge=100, le=40000)
    # Clair de lune : liste complète des canaux allumés la nuit (remplace l'ancienne)
    moonlight: Optional[List[MoonlightChannel]] = Field(default=None, max_length=32)
    acclimation_start: Optional[date] = None
    acclimation_days: Optional[int] = Field(default=None, ge=1, le=365)
    acclimation_start_percent: Optional[int] = Field(default=None, ge=5, le=100)


class LightRead(LightBase):
    id: int
    moonlight: List[MoonlightChannel] = Field(default_factory=list)
    channels: List[LightChannelRead] = Field(default_factory=list)
    acclimation_percent: Optional[int] = Field(default=None, description="Facteur d'acclimatation du jour (%)")

    model_config = ConfigDict(from_attributes=True)


class LightControl(BaseModel):
    channel_id: Optional[int] = Field(default=None, description="Absent = tous les canaux")
    mode: ChannelMode
    value: Optional[int] = Field(default=None, ge=0, le=100, description="Intensité du mode manuel (%)")


class LightDemo(BaseModel):
    duration_s: int = Field(default=60, ge=10, le=600, description="Durée de la journée accélérée")


class LightProfileApply(BaseModel):
    profile: str
    moonlight: bool = False
    # Heure de début souhaitée (minutes depuis minuit) : tout le profil est décalé d'autant
    start: Optional[int] = Field(default=None, ge=0, lt=1440)


class LightScheduleCopy(BaseModel):
    source_channel_id: int
    target_channel_ids: List[int] = Field(min_length=1)


class SpectrumRead(BaseModel):
    key: str
    label: str
    color: str


class ProfileRead(BaseModel):
    key: str
    label: str
    description: str
    # Début et fin du programme par défaut (minutes depuis minuit)
    start: int
    end: int


class LightCatalogRead(BaseModel):
    spectra: List[SpectrumRead]
    profiles: List[ProfileRead]
    # Fuseau horaire des contrôleurs (firmware) : repère « maintenant » des graphiques
    timezone: str


class LightDemoRead(BaseModel):
    light_id: int
    duration_s: Optional[int] = None
    status: Literal["started", "stopped"]
