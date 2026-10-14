"""
showcase.py

Vitrine des boutures (page sans compte) : lien permanent désactivé par défaut,
liens de partage privés (une bourse, une personne) et réservations envoyées
par les visiteurs.
"""

from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import JSON, TIMESTAMP, Boolean, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from middleware.database import Base
from settings import settings as app_settings


def local_today() -> date:
    return datetime.now(ZoneInfo(app_settings.timezone)).date()


class ShowcaseSettings(Base):
    __tablename__ = "showcase_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Lien permanent /vitrine, ouvert à tous : désactivé par défaut
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    title: Mapped[str] = mapped_column(String(80), nullable=False, default="Mes boutures de coraux")
    intro: Mapped[str] = mapped_column(Text, nullable=False, default="")
    contact: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    show_prices: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    price_label: Mapped[str] = mapped_column(String(30), nullable=False, default="Participation")
    allow_reservations: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ShowcaseLink(Base):
    """Lien de partage privé : adresse impossible à deviner, dates d'ouverture, révocable."""

    __tablename__ = "showcase_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    token: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    location_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sale_locations.id", ondelete="SET NULL"), nullable=True
    )
    starts_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ends_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Pendant sa validité, les étiquettes QR scannées par un visiteur mènent à ce lien
    qr_labels: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_viewed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)

    location = relationship("SaleLocation", lazy="joined")

    @property
    def location_name(self) -> Optional[str]:
        return self.location.name if self.location else None

    @property
    def state(self) -> str:
        """active / upcoming / expired / revoked, d'après le jour local."""
        if self.revoked:
            return "revoked"
        today = local_today()
        if self.starts_on and today < self.starts_on:
            return "upcoming"
        if self.ends_on and today > self.ends_on:
            return "expired"
        return "active"


class ShowcaseReservation(Base):
    """Demande d'un visiteur : new -> confirmed (certificat créé) / declined."""

    __tablename__ = "showcase_reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    contact: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # [{"frag_id": 3, "quantity": 2, "reference": "B-2026-0003", "name": "..."}]
    items: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="new", index=True)
    certificate_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("transfer_certificates.id", ondelete="SET NULL"), nullable=True
    )
    # Lien de partage par lequel le visiteur est arrivé (None = lien permanent)
    link_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("showcase_links.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)

    link = relationship("ShowcaseLink", lazy="joined")

    @property
    def link_label(self) -> Optional[str]:
        return self.link.label if self.link else None

    @property
    def link_location_id(self) -> Optional[int]:
        return self.link.location_id if self.link else None
