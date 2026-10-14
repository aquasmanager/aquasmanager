from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

EntityType = Literal["corals", "invertebrates", "fish"]


class DocumentLinkIn(BaseModel):
    entity_type: EntityType
    entity_id: int = Field(gt=0)


class CitesEntry(BaseModel):
    number: str = Field(min_length=1, max_length=60)
    # Espèce du catalogue de coraux concernée (facultatif)
    coral_species_id: Optional[int] = Field(default=None, gt=0)
    coral_species_name: Optional[str] = None


class PurchaseDocumentBase(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    supplier: str = Field(default="", max_length=120)
    purchase_date: Optional[date] = None
    reference: str = Field(default="", max_length=80)
    # Plusieurs numéros CITES ; cites_number = les mêmes, un par ligne (compatibilité)
    cites_numbers: list[str] = Field(default_factory=list, max_length=50)
    cites_number: str = Field(default="", max_length=3000)
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("cites_numbers")
    @classmethod
    def _numbers_length(cls, numbers: list[str]) -> list[str]:
        if any(len(n.strip()) > 60 for n in numbers):
            raise ValueError("Un numéro CITES fait 60 caractères au plus.")
        return numbers


class PurchaseDocumentCreate(PurchaseDocumentBase):
    links: list[DocumentLinkIn] = Field(default_factory=list, max_length=200)
    # Numéros avec leur espèce : remplace cites_numbers s'il est fourni
    cites_entries: Optional[list[CitesEntry]] = Field(default=None, max_length=50)


class PurchaseDocumentUpdate(BaseModel):
    """Champ absent = inchangé ; links = liste complète des spécimens liés."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    supplier: Optional[str] = Field(default=None, max_length=120)
    purchase_date: Optional[date] = None
    reference: Optional[str] = Field(default=None, max_length=80)
    cites_numbers: Optional[list[str]] = Field(default=None, max_length=50)
    cites_number: Optional[str] = Field(default=None, max_length=3000)
    notes: Optional[str] = Field(default=None, max_length=2000)
    links: Optional[list[DocumentLinkIn]] = Field(default=None, max_length=200)
    cites_entries: Optional[list[CitesEntry]] = Field(default=None, max_length=50)


class DocumentFileRead(BaseModel):
    id: int
    original_name: str
    content_type: str
    size: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentLinkRead(BaseModel):
    entity_type: EntityType
    entity_id: int
    # Libellé du spécimen (« Acropora 40 · Bac récifal »), None s'il a été supprimé
    label: Optional[str] = None
    aquarium_id: Optional[int] = None


class PurchaseDocumentRead(PurchaseDocumentBase):
    id: int
    created_at: datetime
    files: list[DocumentFileRead]
    links: list[DocumentLinkRead]
    # Coraux liés automatiquement par leur numéro CITES lors de cet enregistrement
    auto_linked: int = 0
    cites_entries: list[CitesEntry] = Field(default_factory=list)


class CitesSuggestion(BaseModel):
    """Numéro CITES d'une facture pour une espèce (ajout d'un corail)."""

    number: str
    document_id: int
    document_title: str
    supplier: str = ""
    purchase_date: Optional[date] = None
    # Coraux portant déjà ce numéro
    used_by: list[str] = Field(default_factory=list)


class LinkableSpecimen(BaseModel):
    entity_type: EntityType
    entity_id: int
    name: str
    scientific_name: str = ""
    cites: str = ""
    aquarium_id: int
    aquarium_name: str
