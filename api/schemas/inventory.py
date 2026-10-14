from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class InventoryMovementCreate(BaseModel):
    delta: float
    note: Optional[str] = Field(default=None, max_length=200)


class InventoryMovementRead(BaseModel):
    id: int
    item_id: int
    delta: float
    note: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InventoryItemBase(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    unit: str = Field(min_length=1, max_length=20)
    low_stock_threshold: Optional[float] = None
    # Date d'ouverture du conditionnement en cours (ex. réactif de test KH)
    opened_on: Optional[date] = None


class InventoryItemCreate(InventoryItemBase):
    aquarium_id: int = Field(gt=0)
    quantity: float = 0
    # Aquariums concernés : « single » (aquarium_id), « multiple » (aquarium_ids) ou « all »
    scope: Literal["single", "multiple", "all"] = "single"
    aquarium_ids: list[int] = Field(default_factory=list)


class InventoryItemUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    unit: Optional[str] = Field(default=None, min_length=1, max_length=20)
    low_stock_threshold: Optional[float] = None
    opened_on: Optional[date] = None
    scope: Optional[Literal["single", "multiple", "all"]] = None
    aquarium_ids: Optional[list[int]] = None


class InventoryItemRead(InventoryItemBase):
    id: int
    aquarium_id: int
    quantity: float
    scope: str = "single"
    aquarium_ids: list[int] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
