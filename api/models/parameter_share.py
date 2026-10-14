"""
parameter_share.py

Lien public en lecture seule vers les paramètres d'eau d'un aquarium
(forum, club, magasin) : adresse impossible à deviner, date d'expiration,
révocable (suppression). Aucun compte requis pour le consulter.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from middleware.database import Base


class ParameterShareLink(Base):
    __tablename__ = "parameter_share_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    token: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    aquarium_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aquariums.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    # Historique montré : 0 = dernières valeurs seulement
    history_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    # Seulement les paramètres favoris (étoile)
    pinned_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_viewed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)

    aquarium = relationship("Aquarium")

    @property
    def state(self) -> str:
        """active / expired (révoquer = supprimer le lien)."""
        if self.expires_at and datetime.now() > self.expires_at:
            return "expired"
        return "active"
