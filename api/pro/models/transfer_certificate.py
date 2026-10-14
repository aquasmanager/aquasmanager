"""
transfer_certificate.py

Certificats de cession de boutures. Les informations du cédant, de
l'acquéreur et des boutures sont figées dans le certificat (copies) : le
document signé ne change plus, même si une bouture ou le profil du cédant
est modifié ensuite.

- draft     : en attente de la signature de l'acquéreur (lien à jeton)
- signed    : signé, boutures passées « cédées »
"""

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import DATE, JSON, TIMESTAMP, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from middleware.database import Base


class SaleLocation(Base):
    """Lieu de vente (domicile, bourse de Brest...) pour ranger les cessions."""

    __tablename__ = "sale_locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)


class TransferCertificate(Base):
    __tablename__ = "transfer_certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="draft", index=True)
    transfer_date: Mapped[date] = mapped_column(DATE, nullable=False, default=date.today)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sale_locations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    seller: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    seller_signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    legal_mention: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Mention d'information RGPD montrée à l'acquéreur, figée à la création
    privacy_notice: Mapped[str] = mapped_column(Text, nullable=False, default="")
    buyer: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    buyer_signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    # Données de l'acquéreur effacées (durée de conservation dépassée ou demande d'effacement)
    anonymized_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    sign_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    token_expires_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)

    items: Mapped[List["TransferCertificateItem"]] = relationship(
        back_populates="certificate", cascade="all, delete-orphan", order_by="TransferCertificateItem.id"
    )
    location: Mapped[Optional[SaleLocation]] = relationship()

    @property
    def location_name(self) -> Optional[str]:
        return self.location.name if self.location else None

    @property
    def total_price(self) -> Optional[float]:
        prices = [item.price * item.quantity for item in self.items if item.price is not None]
        return round(sum(prices), 2) if prices else None

    @property
    def total_quantity(self) -> int:
        return sum(item.quantity for item in self.items)

    @property
    def buyer_name(self) -> Optional[str]:
        if not self.buyer:
            return None
        return " ".join(p for p in (self.buyer.get("first_name"), self.buyer.get("last_name")) if p) or None


class TransferCertificateItem(Base):
    """Bouture cédée, copiée au moment de la création du certificat."""

    __tablename__ = "transfer_certificate_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    certificate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("transfer_certificates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    frag_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("frags.id", ondelete="SET NULL"), nullable=True)
    reference: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    scientific_name: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    cites: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    origin: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    mother_name: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    # Provenance du pied mère (où il a été acquis), figée à la cession
    mother_acquired_from: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    cut_date: Mapped[Optional[date]] = mapped_column(DATE, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Prix unitaire
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    certificate: Mapped[TransferCertificate] = relationship(back_populates="items")


class SellerProfile(Base):
    """Informations du cédant (une seule ligne), reprises dans chaque certificat."""

    __tablename__ = "seller_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    last_name: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    address: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    postal_code: Mapped[str] = mapped_column(String(12), nullable=False, default="")
    city: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    legal_mention: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # RGPD : mention d'information (vide = texte par défaut) et durée de conservation
    # des données des acquéreurs, en années (0 = pas d'anonymisation automatique)
    privacy_notice: Mapped[str] = mapped_column(Text, nullable=False, default="")
    buyer_retention_years: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now, onupdate=datetime.now)
