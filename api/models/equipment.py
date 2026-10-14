"""
Équipements pilotés par un contrôleur (pompe, chauffage, osmolateur, lampe...).
"""

import enum
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import relationship, Mapped, mapped_column, validates
from sqlalchemy import Integer, String, ForeignKey, TIMESTAMP, Boolean, Enum
from sqlalchemy.sql.schema import UniqueConstraint
from middleware.database import Base
from models.equipment_group import group_equipment_association



class EquipmentStatus(enum.Enum):
    ON = "ON"
    OFF = "OFF"


class EquipmentMode(enum.Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"


class EquipmentCategory(enum.Enum):
    OSMOLATOR = "OSMOLATOR"
    OSMOSEUR = "OSMOSEUR"
    PUMP = "PUMP"
    BRASSAGE = "BRASSAGE"
    ECUMOR = "ECUMOR"
    COOLER = "COOLER"
    HEATER = "HEATER"
    LIGHT = "LIGHT"
    OTHER = "OTHER"


class PhysicalContact(enum.Enum):
    NC = "NC"
    NO = "NO"


class Equipment(Base):
    """Équipement piloté par un relais du contrôleur (pompe, chauffage, osmolateur...)."""

    __tablename__ = "equipments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    aquarium_id: Mapped[int] = mapped_column(Integer, ForeignKey("aquariums.id"), nullable=False)
    controller_id: Mapped[int] = mapped_column(Integer, ForeignKey("controllers.id", ondelete="CASCADE"), nullable=False)
    pin_id: Mapped[int] = mapped_column(Integer, ForeignKey("controllers_pins.id", ondelete="RESTRICT"), nullable=False)
    # Unique par aquarium (vérifié par l'API) ; le nom technique reste unique partout
    name: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    technical_name: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    # Nom technique encore utilisé par le firmware flashé quand technical_name a
    # changé depuis (renommage) ; vidé au flash suivant. NULL = firmware à jour.
    deployed_technical_name: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    status: Mapped[EquipmentStatus] = mapped_column(Enum(EquipmentStatus, validate_strings=True), nullable=False)
    mode: Mapped[EquipmentMode] = mapped_column(Enum(EquipmentMode, validate_strings=True), nullable=False)
    category: Mapped[EquipmentCategory] = mapped_column(Enum(EquipmentCategory, validate_strings=True), nullable=False)
    inverted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    physical_contact: Mapped[PhysicalContact] = mapped_column(Enum(PhysicalContact, validate_strings=True), nullable=False)
    restart_delay: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # Délai avant redémarrage si ON par defaut
    # Durée maximale de fonctionnement (s) : coupure de sécurité des osmolateurs (45 s si vide)
    max_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)

    # RELATIONS CORRIGÉES AU SINGULIER
    controller: Mapped["Controller"] = relationship(back_populates="equipments")
    aquarium: Mapped["Aquarium"] = relationship(back_populates="equipments")
    pin: Mapped["ControllerPin"] = relationship(back_populates="equipment")

    # Broche affichée dans l'interface (comme pour les capteurs)
    @property
    def pin_number(self) -> Optional[str]:
        return self.pin.pin_number if self.pin else None

    @property
    def module_id(self) -> Optional[int]:
        return self.pin.module_id if self.pin else None

    @property
    def module_number(self) -> Optional[int]:
        return self.pin.io_module.number if self.pin and self.pin.io_module else None
    rules: Mapped[list["Rule"]] = relationship(
        "Rule",
        primaryjoin="Equipment.id == Rule.equipment_id",
        back_populates="equipment",
        cascade="all, delete-orphan"
    )
    groups: Mapped[list["EquipmentGroup"]] = relationship(
        "EquipmentGroup",
        secondary=group_equipment_association,
        back_populates="equipments"
    )
    activations: Mapped[list["EquipmentActivation"]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("controller_id", "pin_id", name="check_equipment_pin_unique"),
        {'extend_existing': True}
    )

    @validates("status")
    def validate_status(self, key, value):
        if isinstance(value, EquipmentStatus):
            return value
        if isinstance(value, str) and value in EquipmentStatus._member_map_:
            return EquipmentStatus(value)
        raise ValueError(f"Statut invalide: {value}")

    @validates("physical_contact")
    def validate_physical_contact(self, key, value):
        if isinstance(value, PhysicalContact):
            return value
        if isinstance(value, str) and value in PhysicalContact._member_map_:
            return PhysicalContact(value)
        raise ValueError(f"Contact physique invalide: {value}")