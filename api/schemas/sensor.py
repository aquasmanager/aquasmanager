import re
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List

# Liste centralisée des types de capteurs autorisés
ALLOWED_SENSOR_TYPES = ['sensor', 'binary_sensor', 'niveau', 'temperature', 'ph']


# Seules les sondes de température (DS18B20) et les flotteurs de niveau sont
# gérés par le générateur ESPHome ; le formulaire envoie "temperature" ou
# "niveau", la base stocke "°C" ou "level".
SENSOR_UNITS = {"temperature": "°C", "°c": "°C", "niveau": "level", "level": "level"}


def normalize_sensor_unit(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    unit = SENSOR_UNITS.get(v.strip().lower())
    if unit is None:
        raise ValueError("Mesure non gérée : température ou niveau uniquement")
    return unit


def normalize_one_wire_address(v: Optional[str]) -> Optional[str]:
    """Accepte 0x28ff..., 28ff..., 28:FF:... ; renvoie le format ESPHome 0x + 16 hex."""
    if v is None:
        return None
    cleaned = re.sub(r"[\s:\-]", "", v.strip()).lower()
    if cleaned.startswith("0x"):
        cleaned = cleaned[2:]
    if not cleaned:
        return None
    if not re.fullmatch(r"[0-9a-f]{16}", cleaned):
        raise ValueError("Adresse 1-Wire invalide : 16 caractères hexadécimaux attendus (ex : 0x1c0000031edd2a28)")
    return f"0x{cleaned}"


class SensorBase(BaseModel):
    name: str = Field(..., min_length=1, description="Nom lisible du capteur")
    technical_name: str = Field(..., min_length=1, description="Nom technique unique utilisé pour les topics MQTT")
    aquarium_id: int = Field(..., gt=0, description="ID de l'aquarium associé")
    controller_id: int = Field(..., gt=0, description="ID du contrôleur physique associé")
    pin_id: int = Field(..., ge=0, description="ID de la broche (pin) connectée")
    type: str = Field(..., description="Type de capteur (ex: sensor, binary_sensor)")
    unit: Optional[str] = Field(None, description="Unité de mesure (ex: °C, %, pH)")
    last_value: Optional[float] = Field(None, description="Dernière valeur enregistrée")
    created_at: datetime = Field(..., description="Date de création du capteur")
    is_inverted: bool = Field(False, description="Indique si la valeur logique du capteur binaire doit être inversée (0/1)")
    address: Optional[str] = Field(None, max_length=30, description="Adresse ROM 1-Wire (ex: sonde DS18B20)")
    interval: Optional[int] = Field(None, gt=0, description="Intervalle de lecture en secondes")

    @field_validator('type')
    @classmethod
    def validate_sensor_type(cls, v: str) -> str:
        if v not in ALLOWED_SENSOR_TYPES:
            raise ValueError(f"Le type de capteur doit être l'un de : {ALLOWED_SENSOR_TYPES}")
        return v


class SensorCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Nom lisible du capteur")
    aquarium_id: int = Field(..., gt=0, description="ID de l'aquarium associé")
    controller_id: int = Field(..., gt=0, description="ID du contrôleur physique associé")
    pin_id: int = Field(..., ge=0, description="ID de la broche (pin) connectée")
    type: str = Field(..., description="Type de capteur (ex: sensor, binary_sensor)")
    unit: Optional[str] = Field(None, description="Unité de mesure (ex: °C, %, pH)")
    address: Optional[str] = Field(None, max_length=30, description="Adresse ROM 1-Wire (ex: sonde DS18B20)")
    interval: Optional[int] = Field(None, gt=0, description="Intervalle de lecture en secondes")
    # Flotteur monté à l'envers : « niveau haut » quand la broche est au niveau bas
    is_inverted: bool = Field(False, description="Inversion logique du capteur binaire")

    @field_validator('type')
    @classmethod
    def validate_sensor_type(cls, v: str) -> str:
        if v not in ALLOWED_SENSOR_TYPES:
            raise ValueError(f"Le type de capteur doit être l'un de : {ALLOWED_SENSOR_TYPES}")
        return v

    @field_validator('address')
    @classmethod
    def validate_address(cls, v: Optional[str]) -> Optional[str]:
        return normalize_one_wire_address(v)

    @field_validator('unit')
    @classmethod
    def validate_unit(cls, v: Optional[str]) -> Optional[str]:
        return normalize_sensor_unit(v)


class SensorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, description="Nom lisible du capteur")
    aquarium_id: Optional[int] = Field(None, gt=0, description="ID de l'aquarium associé")
    controller_id: Optional[int] = Field(None, gt=0, description="ID du contrôleur physique associé")
    pin_id: Optional[int] = Field(None, ge=0, description="ID de la broche (pin) connectée")
    type: Optional[str] = Field(None, description="Type de capteur")
    unit: Optional[str] = Field(None, description="Unité de mesure")
    created_at: Optional[datetime] = Field(None, description="Date de création")
    last_value: Optional[float] = Field(None, description="Dernière valeur enregistrée")
    is_inverted: Optional[bool] = Field(None, description="Inversion logique du capteur")
    address: Optional[str] = Field(None, max_length=30, description="Adresse ROM 1-Wire (ex: sonde DS18B20)")
    interval: Optional[int] = Field(None, gt=0, description="Intervalle de lecture en secondes")

    @field_validator('type')
    @classmethod
    def validate_sensor_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_SENSOR_TYPES:
            raise ValueError(f"Le type de capteur doit être l'un de : {ALLOWED_SENSOR_TYPES}")
        return v

    @field_validator('address')
    @classmethod
    def validate_address(cls, v: Optional[str]) -> Optional[str]:
        return normalize_one_wire_address(v)

    @field_validator('unit')
    @classmethod
    def validate_unit(cls, v: Optional[str]) -> Optional[str]:
        return normalize_sensor_unit(v)


class SensorRead(SensorBase):
    id: int = Field(..., gt=0, description="ID unique du capteur en base de données")
    pin_number: Optional[str] = Field(None, description="Numéro de la pin")
    module_id: Optional[int] = Field(None, description="ID du module d'E/S (si PCF)")
    module_number: Optional[int] = Field(None, description="Numéro du module d'E/S sur son contrôleur")
    # Dernière mesure reçue (vide : jamais mesurée)
    last_reading_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SensorListResponse(BaseModel):
    total: int = Field(..., ge=0, description="Nombre total de capteurs")
    sensors: List[SensorRead] = Field(..., description="Liste des capteurs")

