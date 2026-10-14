"""
group_order.py

Commandes groupées (VPC) : les annonces vivent sur le hub de l'éditeur ;
l'installation garde seulement ses jetons (annonces créées, participations)
et les départements suivis.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Integer, String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from middleware.database import Base


class GroupOrderLink(Base):
    __tablename__ = "group_order_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hub_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # owner : annonce créée ici ; participant : participation envoyée d'ici
    role: Mapped[str] = mapped_column(String(12), nullable=False)
    # Jeton secret donné par le hub (gère l'annonce ou la participation)
    token: Mapped[str] = mapped_column(String(80), nullable=False)
    participant_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    # Participants déjà signalés à l'organisateur (notification des nouveaux)
    known_members: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)


class GroupOrderSettings(Base):
    __tablename__ = "group_order_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    departments: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    notify: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Annonces déjà vues (pas de notification en double)
    seen_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
