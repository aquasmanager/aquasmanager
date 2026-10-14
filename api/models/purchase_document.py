"""
purchase_document.py

Documents d'achat : factures, certificats de cession reçus, permis CITES...
Un document regroupe un ou plusieurs fichiers (PDF, photos recto / verso) et
se lie aux spécimens concernés (coraux, invertébrés, poissons), pour retrouver
l'origine d'un spécimen, ou de ses boutures, en cas de contrôle.
"""

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import DATE, TIMESTAMP, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from middleware.database import Base

LINKABLE_TYPES = ("corals", "invertebrates", "fish")


class PurchaseDocument(Base):
    __tablename__ = "purchase_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    supplier: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    purchase_date: Mapped[Optional[date]] = mapped_column(DATE, nullable=True)
    # Numéro de facture ou de certificat
    reference: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    # Un ou plusieurs numéros CITES, un par ligne (services/cites_links.py)
    cites_number: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Espèce du catalogue de coraux de chaque numéro CITES (JSON {numéro normalisé: id d'espèce}) :
    # à l'ajout d'un corail de cette espèce, le numéro est proposé
    cites_species: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)

    files: Mapped[List["PurchaseDocumentFile"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="PurchaseDocumentFile.id"
    )
    links: Mapped[List["PurchaseDocumentLink"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="PurchaseDocumentLink.id"
    )


class PurchaseDocumentFile(Base):
    __tablename__ = "purchase_document_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("purchase_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Nom sur le disque (généré) et nom d'origine (affiché, téléchargement)
    filename: Mapped[str] = mapped_column(String(60), nullable=False)
    original_name: Mapped[str] = mapped_column(String(200), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)

    document: Mapped[PurchaseDocument] = relationship(back_populates="files")


class PurchaseDocumentLink(Base):
    """Spécimen concerné. Sans clé étrangère : le document reste consultable si le spécimen est supprimé."""

    __tablename__ = "purchase_document_links"
    __table_args__ = (UniqueConstraint("document_id", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("purchase_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    document: Mapped[PurchaseDocument] = relationship(back_populates="links")
