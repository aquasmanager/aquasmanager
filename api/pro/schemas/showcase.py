from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ShowcaseSettingsBase(BaseModel):
    enabled: bool = False
    title: str = Field(default="Mes boutures de coraux", min_length=1, max_length=80)
    intro: str = Field(default="", max_length=2000)
    contact: str = Field(default="", max_length=200)
    show_prices: bool = False
    price_label: str = Field(default="Participation", min_length=1, max_length=30)
    allow_reservations: bool = True


class ShowcaseSettingsRead(ShowcaseSettingsBase):
    model_config = ConfigDict(from_attributes=True)


class ShowcaseLot(BaseModel):
    id: int
    reference: str
    name: str
    scientific_name: str
    coral_type: Optional[str] = None
    quantity: int
    price: Optional[float] = None


class PublicShowcase(BaseModel):
    title: str
    intro: str
    contact: str
    show_prices: bool
    price_label: str
    allow_reservations: bool
    # Lien de partage utilisé (None = lien permanent)
    link_label: Optional[str] = None
    ends_on: Optional[date] = None
    lots: list[ShowcaseLot]


class ShowcaseLinkBase(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    starts_on: Optional[date] = None
    ends_on: Optional[date] = None
    qr_labels: bool = False


class ShowcaseLinkCreate(ShowcaseLinkBase):
    location_id: Optional[int] = Field(default=None, gt=0)
    location_name: Optional[str] = Field(default=None, max_length=80)


class ShowcaseLinkUpdate(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=80)
    starts_on: Optional[date] = None
    ends_on: Optional[date] = None
    qr_labels: Optional[bool] = None
    revoked: Optional[bool] = None
    location_id: Optional[int] = Field(default=None, gt=0)
    location_name: Optional[str] = Field(default=None, max_length=80)


class ShowcaseLinkRead(ShowcaseLinkBase):
    id: int
    token: str
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    revoked: bool
    view_count: int
    last_viewed_at: Optional[datetime] = None
    created_at: datetime
    # active / upcoming / expired / revoked
    state: str

    model_config = ConfigDict(from_attributes=True)


class ReservationItem(BaseModel):
    frag_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=99)


class ReservationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    contact: str = Field(min_length=4, max_length=120, description="E-mail ou téléphone")
    message: Optional[str] = Field(default=None, max_length=1000)
    items: list[ReservationItem] = Field(min_length=1, max_length=30)
    # Champ piège anti-robots : doit rester vide
    website: str = Field(default="", max_length=0)


class ReservationRead(BaseModel):
    id: int
    name: str
    contact: str
    message: Optional[str] = None
    items: list[dict]
    status: Literal["new", "confirmed", "declined"]
    certificate_id: Optional[int] = None
    link_id: Optional[int] = None
    link_label: Optional[str] = None
    link_location_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReservationConfirm(BaseModel):
    location_id: Optional[int] = Field(default=None, gt=0)
    location_name: Optional[str] = Field(default=None, max_length=80)
