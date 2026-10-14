"""
Réservation et libération des broches des contrôleurs.

Une broche libre a mode = bus = "FREE". Un équipement (relais) occupe sa
broche seul ; un bus 1-Wire peut porter plusieurs sondes de température,
la broche ne redevient donc libre qu'au départ de la dernière d'entre elles.
"""

from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.controller_pin import ControllerPin
from models.equipment import Equipment
from models.sensor import Sensor


def get_controller_pin(db: Session, pin_id: int, controller_id: int) -> ControllerPin:
    pin = db.query(ControllerPin).filter(ControllerPin.id == pin_id).first()
    if not pin:
        raise HTTPException(status_code=404, detail="La broche n'existe pas.")
    if pin.controller_id != controller_id:
        raise HTTPException(status_code=400, detail="Cette broche n'appartient pas au contrôleur choisi.")
    return pin


def pin_is_used(
    db: Session,
    pin_id: int,
    exclude_equipment_id: Optional[int] = None,
    exclude_sensor_id: Optional[int] = None,
) -> bool:
    equipments = db.query(Equipment.id).filter(Equipment.pin_id == pin_id)
    if exclude_equipment_id is not None:
        equipments = equipments.filter(Equipment.id != exclude_equipment_id)
    sensors = db.query(Sensor.id).filter(Sensor.pin_id == pin_id)
    if exclude_sensor_id is not None:
        sensors = sensors.filter(Sensor.id != exclude_sensor_id)
    return equipments.first() is not None or sensors.first() is not None


def ensure_pin_free_for_equipment(db: Session, pin: ControllerPin, equipment_id: Optional[int] = None) -> None:
    """Un relais a besoin d'une broche pour lui seul (et pas celle du bus I2C)."""
    ensure_not_i2c_pin(pin)
    ensure_not_pwm_module_pin(pin)
    if pin_is_used(db, pin.id, exclude_equipment_id=equipment_id) or pin.lights_channel is not None:
        raise HTTPException(status_code=409, detail=f"La broche {pin.pin_number} est déjà utilisée.")


def claim_pin(pin: ControllerPin, bus: str, mode: str, label: str) -> None:
    pin.bus = bus
    pin.mode = mode
    pin.label = label


def release_pin_if_unused(
    db: Session,
    pin_id: Optional[int],
    exclude_equipment_id: Optional[int] = None,
    exclude_sensor_id: Optional[int] = None,
) -> None:
    """Remet la broche à FREE si plus aucun équipement ni capteur ne l'utilise."""
    if pin_id is None:
        return
    if pin_is_used(db, pin_id, exclude_equipment_id=exclude_equipment_id, exclude_sensor_id=exclude_sensor_id):
        return
    pin = db.query(ControllerPin).filter(ControllerPin.id == pin_id).first()
    if pin is not None and pin.lights_channel is None:
        claim_pin(pin, "FREE", "FREE", "FREE")


# Bus I2C de l'ESP32 (horloge RTC, modules d'extension) : SDA = GPIO 21, SCL = GPIO 22
I2C_PINS = {"21": "SDA", "22": "SCL"}


def i2c_active(controller) -> bool:
    return bool(getattr(controller, "rtc_model", None) or getattr(controller, "io_modules", None))


def i2c_role(pin: ControllerPin) -> Optional[str]:
    """« SDA » ou « SCL » si la broche porte le bus I2C du contrôleur, sinon None."""
    if pin.module_id is not None or not i2c_active(pin.controller):
        return None
    return I2C_PINS.get(str(pin.pin_number))


def ensure_not_i2c_pin(pin: ControllerPin) -> None:
    role = i2c_role(pin)
    if role:
        raise HTTPException(
            status_code=409,
            detail=f"GPIO {pin.pin_number} porte le bus I2C ({role}) de l'horloge et des modules : choisis une autre broche.",
        )


def pwm_module(pin: ControllerPin) -> bool:
    module = pin.io_module
    return module is not None and str(getattr(module.type, "value", module.type)) == "PCA9685"


def ensure_not_pwm_module_pin(pin: ControllerPin) -> None:
    if pwm_module(pin):
        raise HTTPException(
            status_code=409,
            detail="Les canaux d'un module PCA9685 sont des sorties PWM, réservées aux canaux de lampe.",
        )
