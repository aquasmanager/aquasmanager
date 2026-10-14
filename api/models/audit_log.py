"""
audit_log.py

Journal d'activité : qui a fait quoi (création, modification, suppression,
commande d'un équipement, flash, connexion...). Alimenté automatiquement par
middleware/audit.py pour toute requête d'écriture.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from middleware.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now, index=True)
    # Pas de clé étrangère : le journal survit à la suppression du compte
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    # Libellé lisible de l'action (ex. « Suppression de l'équipement »)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    entity_label: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    # Résumé des champs envoyés (sans mot de passe ni jeton), en JSON
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    client_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
