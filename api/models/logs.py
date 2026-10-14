"""
Journaux envoyés par les contrôleurs.
"""

from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, ForeignKey
from middleware.database import Base


class LogModel(Base):
    """Ligne de journal d'un contrôleur (niveau, composant ESPHome, message)."""

    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    controller_id: Mapped[int] = mapped_column(ForeignKey("controllers.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(default=datetime.now)
    level: Mapped[str] = mapped_column(String(10), index=True)  # ex: I (INFO), W (WARN), E (ERROR)
    component: Mapped[str] = mapped_column(String(50), index=True)  # ex: safe_mode, wifi, mqtt
    message: Mapped[str] = mapped_column(Text)

    controller: Mapped["Controller"] = relationship(back_populates="logs")
