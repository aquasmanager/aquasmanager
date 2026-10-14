"""
frag.py

Boutures de coraux : chaque bouture garde les informations réglementaires de
son pied mère (espèce, n° CITES, provenance) au moment du bouturage, pour
rester exploitable même si le corail d'origine est modifié ou supprimé.

Une fiche est un lot de boutures identiques : quantity = nombre encore
disponible. Les boutures cédées sont décomptées de ce nombre dès la création
du certificat (réservées), définitivement à sa signature.

Statut (recalculé, voir services/frags.refresh_frag_status) : available s'il
en reste, sinon reserved (certificat en attente), transferred (tout cédé) ou
empty (épuisé sans cession : pertes, dons...).
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import DATE, TIMESTAMP, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from middleware.database import Base

FRAG_STATUSES = ("available", "reserved", "transferred", "empty")


class Frag(Base):
    __tablename__ = "frags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    reference: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    # Bac où se trouve la bouture (vide si l'aquarium a été supprimé : l'historique est gardé)
    aquarium_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("aquariums.id", ondelete="SET NULL"), nullable=True, index=True
    )
    mother_coral_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("corals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    mother_name: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    scientific_name: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    coral_type: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    cites: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    origin: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    # Provenance du pied mère (magasin, bourse, particulier), reprise du corail
    acquired_from: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    cut_date: Mapped[date] = mapped_column(DATE, nullable=False, default=date.today)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Prix unitaire indicatif
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="available", index=True)
    # Lot masqué de la vitrine publique
    showcase_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Dernier certificat de cession où figure la bouture
    certificate_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("transfer_certificates.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)

    # Quantités réservées / cédées, calculées à la lecture (services/frags.attach_counts)
    reserved_quantity = 0
    transferred_quantity = 0

    certificate: Mapped[Optional["TransferCertificate"]] = relationship(foreign_keys=[certificate_id])  # noqa: F821
    movements: Mapped[list["FragMovement"]] = relationship(
        cascade="all, delete-orphan", order_by="FragMovement.id", passive_deletes=True
    )

    @property
    def certificate_number(self) -> Optional[str]:
        return self.certificate.number if self.certificate else None


# Raisons d'un mouvement de quantité
MOVEMENT_REASONS = ("created", "added", "lost", "gift", "correction", "reserved", "released", "moved")


class FragMovement(Base):
    """
    Historique des quantités d'un lot : création, ajouts, pertes, dons,
    corrections et réservations / libérations par les certificats. Sert au
    suivi (survie par espèce / pied mère).
    """

    __tablename__ = "frag_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    frag_id: Mapped[int] = mapped_column(Integer, ForeignKey("frags.id", ondelete="CASCADE"), nullable=False, index=True)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(12), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    certificate_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)
