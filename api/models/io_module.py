"""
Modules d'entrées/sorties raccordés à un contrôleur (extensions I2C...).
"""

import enum
from typing import List
from sqlalchemy import Integer, String, Enum
from sqlalchemy.orm import relationship, Mapped, mapped_column, validates
from sqlalchemy.sql.schema import ForeignKey, UniqueConstraint, CheckConstraint
from middleware.database import Base


class ModuleType(str, enum.Enum):
    PCF8574 = "PCF8574"
    PCF8575 = "PCF8575"
    # 16 sorties PWM (canaux de lampe), adresse 0x40 par défaut
    PCA9685 = "PCA9685"

    def __str__(self):
        return self.value


class IoModule(Base):
    """class IoModule"""

    __tablename__ = "io_modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    controller_id: Mapped[int] = mapped_column(Integer, ForeignKey("controllers.id", ondelete="CASCADE"), nullable=False)
    address: Mapped[str] = mapped_column(String(10), nullable=False)  # 0X20, ...
    # Numéro affiché (« Module 1 », « Module 2 »...), unique par contrôleur
    number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    type: Mapped[ModuleType] = mapped_column(Enum(ModuleType, validate_strings=True), nullable=False)  # PCF8574, ...

    # RELATIONS CORRIGÉES AU SINGULIER
    controller: Mapped["Controller"] = relationship(back_populates="io_modules")
    pins: Mapped[List["ControllerPin"]] = relationship("ControllerPin", back_populates="io_module", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('controller_id', 'address', name='_controller_address_uc'),
        CheckConstraint("type IN ('PCF8574', 'PCF8575', 'PCA9685')", name="check_type"),
    )

    @validates("type")
    def validate_type(self, key, value):
        if isinstance(value, ModuleType):
            return value
        if isinstance(value, str) and value in ModuleType._member_map_:
            return ModuleType(value)
        raise ValueError(f"Type invalide: {value}")