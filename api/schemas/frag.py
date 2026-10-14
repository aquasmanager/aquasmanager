from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

FragStatus = Literal["available", "reserved", "transferred", "empty"]


class FragCreate(BaseModel):
    """Champs vides : repris du pied mère (mother_coral_id)."""

    mother_coral_id: Optional[int] = Field(default=None, gt=0)
    aquarium_id: Optional[int] = Field(default=None, gt=0, description="Bac de la bouture (celui du pied mère par défaut)")
    name: Optional[str] = Field(default=None, max_length=60)
    scientific_name: Optional[str] = Field(default=None, max_length=60)
    coral_type: Optional[Literal["SPS", "LPS", "MOU"]] = None
    cites: Optional[str] = Field(default=None, max_length=30)
    origin: Optional[str] = Field(default=None, max_length=100, description="Provenance")
    acquired_from: Optional[str] = Field(default=None, max_length=120, description="Provenance du pied mère")
    cut_date: Optional[date] = None
    price: Optional[float] = Field(default=None, ge=0, description="Prix unitaire")
    notes: Optional[str] = None
    quantity: int = Field(default=1, ge=1, le=9999, description="Nombre de boutures du lot")


class FragUpdate(BaseModel):
    aquarium_id: Optional[int] = Field(default=None, gt=0)
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    scientific_name: Optional[str] = Field(default=None, max_length=60)
    coral_type: Optional[Literal["SPS", "LPS", "MOU"]] = None
    cites: Optional[str] = Field(default=None, max_length=30)
    origin: Optional[str] = Field(default=None, max_length=100)
    acquired_from: Optional[str] = Field(default=None, max_length=120)
    cut_date: Optional[date] = None
    price: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = None
    # Nombre encore disponible (les boutures réservées / cédées n'en font plus partie)
    quantity: Optional[int] = Field(default=None, ge=0, le=9999)
    # Raison du changement de quantité (historique, suivi de survie)
    quantity_reason: Literal["added", "lost", "gift", "correction"] = "correction"
    quantity_note: Optional[str] = Field(default=None, max_length=200)
    showcase_hidden: Optional[bool] = None


class FragRead(BaseModel):
    id: int
    reference: str
    aquarium_id: Optional[int] = None
    mother_coral_id: Optional[int] = None
    mother_name: Optional[str] = None
    name: str
    scientific_name: str
    coral_type: Optional[str] = None
    cites: str
    origin: str
    acquired_from: Optional[str] = None
    cut_date: date
    quantity: int
    reserved_quantity: int = 0
    transferred_quantity: int = 0
    price: Optional[float] = None
    notes: Optional[str] = None
    status: FragStatus
    showcase_hidden: bool = False
    certificate_id: Optional[int] = None
    certificate_number: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


MovementReason = Literal["created", "added", "lost", "gift", "correction", "reserved", "released", "moved"]


class FragMovementRead(BaseModel):
    id: int
    delta: int
    reason: MovementReason
    note: Optional[str] = None
    certificate_number: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FragMovementUpdate(BaseModel):
    """Seuls les ajustements manuels peuvent être requalifiés (ex : une perte qui était un don)."""

    reason: Optional[Literal["added", "lost", "gift", "correction"]] = None
    note: Optional[str] = Field(default=None, max_length=200)


class FragStatRow(BaseModel):
    key: str
    name: str
    scientific_name: str = ""
    lots: int
    produced: int
    transferred: int
    reserved: int
    lost: int
    gift: int
    available: int
    survival_rate: Optional[float] = None


class FragMove(BaseModel):
    """Déplacer un ou plusieurs lots vers un bac (None = hors bac)."""

    frag_ids: list[int] = Field(min_length=1, max_length=500)
    aquarium_id: Optional[int] = None
