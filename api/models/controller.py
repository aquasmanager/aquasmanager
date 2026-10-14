"""
Contrôleur (ESP32...) : réseau, horloge, état, configuration flashée, et ses
broches, modules d'extension, équipements, capteurs et lampes.
"""

from datetime import datetime
import enum
from typing import List, Optional
from sqlalchemy import Integer, String, Enum, DateTime, CheckConstraint, Boolean, event
from sqlalchemy.orm import relationship, Mapped, mapped_column, validates
from models.controller_pin import ControllerPin
from middleware.database import Base


class ControllerType(enum.Enum):
    RPI = "RPI"
    ESP32 = "ESP32"
    ESP8266 = "ESP8266"
    ARDUINO = "ARDUINO"


CONTROLLER_PINS = {
    ControllerType.RPI.value: [2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27],
    ControllerType.ESP32.value: [2, 4, 5, 12, 13, 14, 15, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33, 34, 35],
    ControllerType.ARDUINO.value: ["A0", "A1", "A2", "A3", "A4", "A5", 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
    ControllerType.ESP8266.value: [0, 2, 4, 5, 12, 13, 14, 15, 16]
}


class Controller(Base):
    """Modèle représentant un contrôleur physique ou microcontrôleur."""

    __tablename__ = "controllers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    name: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    technical_name: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    type: Mapped[ControllerType] = mapped_column(Enum(ControllerType), nullable=False)
    ip: Mapped[Optional[str]] = mapped_column(String(15), unique=True, nullable=True, index=True)
    zone: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OFFLINE")
    is_dirty: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_sync: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=False, default=datetime.now)
    yaml_config: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Horloge temps réel sur pile (module I2C) : heure juste au démarrage même sans réseau
    rtc_model: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    # Fréquence du bus I2C en kHz (horloge, modules d'extension) ; baisser pour un câble long
    i2c_frequency_khz: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    last_config: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    pins: Mapped[List["ControllerPin"]] = relationship("ControllerPin", back_populates="controller", cascade="all, delete-orphan")
    equipments: Mapped[List["Equipment"]] = relationship("Equipment", back_populates="controller", cascade="all, delete-orphan")
    sensors: Mapped[List["Sensor"]] = relationship("Sensor", back_populates="controller", cascade="all, delete-orphan")
    lights: Mapped[List["Light"]] = relationship("Light", back_populates="controller", cascade="all, delete-orphan")
    io_modules: Mapped[List["IoModule"]] = relationship("IoModule", back_populates="controller", cascade="all, delete-orphan")
    logs: Mapped[list["LogModel"]] = relationship("LogModel", back_populates="controller", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("type IN ('RPI', 'ESP32', 'ESP8266', 'ARDUINO')", name="check_controller_type"),
    )

    @validates("type")
    def validate_type(self, key, value):
        if isinstance(value, ControllerType):
            return value
        if isinstance(value, str) and value in ControllerType._value2member_map_:
            return ControllerType(value)
        raise ValueError(f"Type invalide: {value}")


# Écouteur d'événement SQLAlchemy placé EN DEHORS de la classe
@event.listens_for(Controller, "after_insert")
def populate_pins(mapper, connection, target):
    """Génère automatiquement la liste des pins par défaut lors de la création d'un contrôleur."""
    type_val = target.type.value if isinstance(target.type, ControllerType) else target.type
    pin_numbers = CONTROLLER_PINS.get(type_val, [])

    if not pin_numbers:
        return

    connection.execute(
        ControllerPin.__table__.insert(),
        [
            {
                "controller_id": target.id,
                "pin_number": str(n),
                "bus": "FREE",
                "mode": "FREE"
            }
            for n in pin_numbers
        ]
    )