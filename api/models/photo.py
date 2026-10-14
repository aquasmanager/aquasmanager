"""
Photos rattachées aux fiches (aquarium, vivants, frags...).
"""

from datetime import datetime
import enum
from sqlalchemy import Integer, String, DateTime, Boolean, Enum
from sqlalchemy.orm import Mapped, mapped_column, validates

from middleware.database import Base


class PhotoType(enum.Enum):
    """Type d'élément auquel une photo est rattachée."""

    aquariums = "aquariums"
    corals = "corals"
    fishes = "fishes"
    plants = "plants"
    invertebrates = "invertebrates"
    frags = "frags"

    def __str__(self):
        return self.value

    @classmethod
    def _missing_(cls, value):
        # Ancien nom (URL /photos/other_alives/...) le temps de la transition
        return cls.invertebrates if value == "other_alives" else None


class Photo(Base):
    """Photo d'un aquarium, d'un vivant ou d'une bouture (fichier dans uploads/)."""
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, primary_key=True, index=True)

    entity_type: Mapped[PhotoType] = mapped_column(Enum(PhotoType, validate_strings=True), nullable=False)

    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=datetime.now, nullable=False)
    is_main: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    @validates("entity_type")
    def validate_entity_type(self, key, value):
        if isinstance(value, PhotoType):
            return value
        if isinstance(value, str) and value in PhotoType._member_map_:
            return PhotoType(value)
        raise ValueError(f"Type d'entité invalide: {value}")