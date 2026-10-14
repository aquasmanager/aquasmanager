"""
Jetons de rafraîchissement des sessions (stockés hachés, révocables).
"""

from datetime import datetime
from sqlalchemy import Integer, String, DateTime
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql.schema import ForeignKey
from middleware.database import Base


class RefreshToken(Base):
    """Jeton de rafraîchissement d'une session (cookie), révocable."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # RELATION CORRIGÉES AU SINGULIER
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")