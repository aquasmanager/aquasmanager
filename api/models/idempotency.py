"""
idempotency.py

Réponses déjà envoyées pour une clé d'idempotence (en-tête Idempotency-Key) :
une requête rejouée par l'appli hors connexion n'est appliquée qu'une fois.
"""

from datetime import datetime

from sqlalchemy import TIMESTAMP, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from middleware.database import Base


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False, default="application/json")
    body: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, default=b"")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now, index=True)
