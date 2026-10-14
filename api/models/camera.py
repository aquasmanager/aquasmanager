"""
camera.py

Caméras IP d'un aquarium (optionnel). Le flux RTSP est relayé par go2rtc :
le navigateur ne voit jamais l'adresse ni les identifiants de la caméra.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import TIMESTAMP, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from middleware.database import Base


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    aquarium_id: Mapped[int] = mapped_column(Integer, ForeignKey("aquariums.id", ondelete="CASCADE"), nullable=False, index=True)
    # Unique par aquarium (vérifié par l'API)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    # reolink | tapo | rtsp : préremplit les chemins des flux
    brand: Mapped[str] = mapped_column(String(20), nullable=False, default="rtsp")
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=554)
    username: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    # Chiffré (Fernet, clé dérivée de AQUAS_SECRET_KEY), jamais renvoyé au front
    password_encrypted: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Flux principal (plein écran, captures) et secondaire (vignettes, direct léger)
    main_path: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    sub_path: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)

    aquarium: Mapped["Aquarium"] = relationship(back_populates="cameras")
