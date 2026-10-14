"""
Comptes utilisateurs, rôles et préférences.
"""

import enum
from typing import List, Optional

from sqlalchemy import Boolean, Integer, String, Enum
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.orm import validates

from middleware.database import Base


class UserRole(enum.Enum):
    """
    Rôle d'un compte, du plus restreint (consultation) au plus étendu (admin).

    Doit rester alignée avec schemas.user.Role : les deux énumèrent les
    mêmes rôles utilisés par min_role_required().
    """

    consult = "consult"
    # Bourse aux boutures : lecture de tout, écriture limitée aux boutures et cessions
    seller = "seller"
    # Gardiennage (vacances) : tâches, relevés et stock, sans pilotage ni modification
    caretaker = "caretaker"
    user = "user"
    manager = "manager"
    admin = "admin"

    def __str__(self):
        return self.value


class User(Base):
    """Compte de l'application (identifiant, mot de passe chiffré, rôle, langue)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False)

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, validate_strings=True),
        nullable=False,
        default=UserRole.user
    )
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Langue de l'interface choisie par l'utilisateur (fr, en) ; vide tant qu'il
    # n'en a pas choisi (celle de l'appareil s'applique alors)
    language: Mapped[Optional[str]] = mapped_column(String(5), nullable=True, default=None)

    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    @validates("role")
    def validate_role(self, key, value):
        if isinstance(value, str):
            try:
                value = UserRole(value)
            except ValueError:
                raise ValueError(f"Role invalide: {value}")
        elif not isinstance(value, UserRole):
            raise ValueError(f"Role invalide: {value}")
        return value