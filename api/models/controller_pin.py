"""controller_pin model"""

import enum
from typing import List, Optional
from sqlalchemy import Integer, String, Enum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.orm.mapper import validates
from sqlalchemy.sql.schema import ForeignKey, UniqueConstraint, CheckConstraint
from middleware.database import Base


class ControllerPinMode(enum.Enum):
    IN = "IN"
    OUT = "OUT"
    SENSOR = "SENSOR"
    FREE = "FREE"


class ControllerPinBus(enum.Enum):
    GPIO = "GPIO"
    PWM = "PWM"
    I2C = "I2C"
    SPI = "SPI"
    ONEWIRE = "1WIRE"
    ADC = "ADC"
    UART = "UART"
    PCF8574 = "PCF8574"
    PCF8575 = "PCF8575"
    NATIVE = "NATIVE"
    FREE = "FREE"


class ControllerPin(Base):
    """class ControllerPin"""

    __tablename__ = "controllers_pins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    controller_id: Mapped[int] = mapped_column(Integer, ForeignKey("controllers.id", ondelete="CASCADE"), nullable=False)
    module_id: Mapped[int] = mapped_column(Integer, ForeignKey("io_modules.id", ondelete="CASCADE"), nullable=True)
    pin_number: Mapped[str] = mapped_column(String(20), nullable=False)  # 17, A0, SDA...
    # values_callable : sans ça, SQLAlchemy sérialise par défaut le NOM du
    # membre ("ONEWIRE") plutôt que sa VALEUR ("1WIRE"), alors que la CHECK
    # constraint check_pin_bus et le code existant (routes/sensor.py::
    # update_pin, écrit en SQL brut) attendent la valeur. Tous les autres
    # membres ont un nom == valeur, ce qui a masqué le bug jusqu'ici : seul
    # ONEWIRE diverge ("1WIRE"), donc jamais déclenché tant qu'aucun capteur
    # température n'avait été créé.
    bus: Mapped[ControllerPinBus] = mapped_column(
        Enum(ControllerPinBus, values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
    )  # GPIO, I2C, SPI...
    mode: Mapped[ControllerPinMode] = mapped_column(Enum(ControllerPinMode), nullable=False)  # IN, OUT, SENSOR
    label: Mapped[str] = mapped_column(String(100), nullable=True)

    # RELATIONS CORRIGÉES AU SINGULIER
    controller: Mapped["Controller"] = relationship(back_populates="pins")
    io_module: Mapped[Optional["IoModule"]] = relationship("IoModule", back_populates="pins")
    equipment: Mapped[Optional["Equipment"]] = relationship(back_populates="pin", uselist=False)
    # Liste (pas un objet unique) : un bus 1-Wire porte plusieurs sondes
    # DS18B20 sur la même broche physique, distinguées par leur adresse.
    sensors: Mapped[List["Sensor"]] = relationship(back_populates="pin")
    lights_channel: Mapped[Optional["LightChannel"]] = relationship(back_populates="pin", uselist=False)

    __table_args__ = (
        UniqueConstraint("controller_id", "module_id", "pin_number", name="check_device_pin_unique"),
        CheckConstraint("bus IN ('GPIO', 'I2C', 'SPI', '1WIRE', 'ADC', 'PWM', 'UART', 'PCF8574', 'PCF8575', 'NATIVE', 'FREE')", name="check_pin_bus"),
        CheckConstraint("mode IN ('IN', 'OUT', 'SENSOR', 'FREE')", name="check_pin_mode")
    )

    @validates("mode")
    def validate_mode(self, key, value):
        if isinstance(value, ControllerPinMode):
            return value
        if isinstance(value, str) and value in ControllerPinMode._member_map_:
            return ControllerPinMode(value)
        raise ValueError(f"Mode invalide: {value}")

    @validates("bus")
    def validate_bus(self, key, value):
        if isinstance(value, ControllerPinBus):
            return value
        if isinstance(value, str):
            if value in ControllerPinBus._value2member_map_:
                return ControllerPinBus(value)
            if value in ControllerPinBus._member_map_:
                return ControllerPinBus[value]
        raise ValueError(f"Bus invalide: {value}")