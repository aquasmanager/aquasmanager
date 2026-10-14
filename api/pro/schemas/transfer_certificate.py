from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

SIGNATURE_MAX_LENGTH = 400_000  # image PNG en data URL



def _check_signature(value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return None
    if not value.startswith("data:image/png;base64,"):
        raise ValueError("Signature invalide (image PNG attendue).")
    if len(value) > SIGNATURE_MAX_LENGTH:
        raise ValueError("Signature trop volumineuse.")
    return value


class SellerProfileBase(BaseModel):
    first_name: str = Field(default="", max_length=60)
    last_name: str = Field(default="", max_length=60)
    address: str = Field(default="", max_length=200)
    postal_code: str = Field(default="", max_length=12)
    city: str = Field(default="", max_length=80)
    email: str = Field(default="", max_length=120)
    phone: str = Field(default="", max_length=30)
    legal_mention: str = Field(default="", max_length=3000)
    # RGPD : vide = mention par défaut ; durée en années, 0 = pas d'anonymisation automatique
    privacy_notice: str = Field(default="", max_length=3000)
    buyer_retention_years: int = Field(default=5, ge=0, le=30)


class SellerProfileUpdate(SellerProfileBase):
    # Absente : signature inchangée ; chaîne vide : signature effacée
    signature: Optional[str] = None

    @field_validator("signature")
    @classmethod
    def _valid_signature(cls, value: Optional[str]) -> Optional[str]:
        return value if value == "" else _check_signature(value)


class SellerProfileRead(SellerProfileBase):
    signature: Optional[str] = None
    complete: bool = False
    # Texte réellement montré à l'acquéreur (celui saisi, sinon le texte par défaut)
    effective_privacy_notice: str = ""

    model_config = ConfigDict(from_attributes=True)


class CertificateItemCreate(BaseModel):
    frag_id: int = Field(gt=0)
    quantity: int = Field(default=1, ge=1, le=9999)
    # Prix unitaire (celui de la bouture si absent)
    price: Optional[float] = Field(default=None, ge=0)


class CertificateCreate(BaseModel):
    items: list[CertificateItemCreate] = Field(min_length=1, max_length=100)
    transfer_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    # Lieu existant (location_id) ou nouveau lieu créé à la volée (location_name)
    location_id: Optional[int] = Field(default=None, gt=0)
    location_name: Optional[str] = Field(default=None, max_length=80)


class CertificateUpdate(BaseModel):
    """Lieu de vente (modifié seulement si location_id / location_name est envoyé)."""

    location_id: Optional[int] = Field(default=None, gt=0)
    location_name: Optional[str] = Field(default=None, max_length=80)


class SaleLocationWrite(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class SaleLocationRead(BaseModel):
    id: int
    name: str
    certificate_count: int = 0
    total_quantity: int = 0
    total_price: Optional[float] = None
    last_transfer_date: Optional[date] = None


class CertificateItemRead(BaseModel):
    id: int
    frag_id: Optional[int] = None
    reference: str
    name: str
    scientific_name: str
    cites: str
    origin: str
    mother_name: Optional[str] = None
    mother_acquired_from: Optional[str] = None
    cut_date: Optional[date] = None
    quantity: int = 1
    price: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class BuyerInfo(BaseModel):
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    address: str = Field(min_length=1, max_length=200)
    postal_code: str = Field(min_length=1, max_length=12)
    city: str = Field(min_length=1, max_length=80)
    email: Optional[str] = Field(default=None, max_length=120, pattern=r"^$|^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: Optional[str] = Field(default=None, max_length=30)


class CertificateSign(BaseModel):
    buyer: BuyerInfo
    signature: str
    accept: Literal[True] = Field(description="L'acquéreur reconnaît avoir reçu les spécimens")

    @field_validator("signature")
    @classmethod
    def _valid_signature(cls, value: str) -> str:
        checked = _check_signature(value)
        if checked is None:
            raise ValueError("La signature est obligatoire.")
        return checked


class OfflineSale(BaseModel):
    """Vente faite sans réseau : certificat créé et signé d'un coup à la synchronisation."""

    items: list[CertificateItemCreate] = Field(min_length=1, max_length=100)
    transfer_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    location_id: Optional[int] = Field(default=None, gt=0)
    location_name: Optional[str] = Field(default=None, max_length=80)
    buyer: BuyerInfo
    signature: str
    signed_at: datetime
    accept: Literal[True]

    @field_validator("signature")
    @classmethod
    def _valid_signature(cls, value: str) -> str:
        checked = _check_signature(value)
        if checked is None:
            raise ValueError("La signature est obligatoire.")
        return checked


class CertificateSummary(BaseModel):
    id: int
    number: str
    status: Literal["draft", "signed"]
    transfer_date: date
    buyer_name: Optional[str] = None
    total_price: Optional[float] = None
    item_count: int
    total_quantity: int
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    created_at: datetime
    signed_at: Optional[datetime] = None
    token_expires_at: datetime
    anonymized_at: Optional[datetime] = None


class CertificateRead(CertificateSummary):
    notes: Optional[str] = None
    seller: dict
    legal_mention: str
    privacy_notice: str = ""
    buyer: Optional[dict] = None
    items: list[CertificateItemRead]
    sign_token: str


class PublicCertificateRead(BaseModel):
    """Vue de l'acquéreur (page de signature) : ni jeton ni signatures."""

    number: str
    status: Literal["draft", "signed"]
    transfer_date: date
    location_name: Optional[str] = None
    notes: Optional[str] = None
    seller: dict
    legal_mention: str
    privacy_notice: str = ""
    buyer: Optional[dict] = None
    items: list[CertificateItemRead]
    total_price: Optional[float] = None
    total_quantity: int
    signed_at: Optional[datetime] = None
