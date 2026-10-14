"""
Capteurs des contrôleurs : création, modification, historique.
"""

import logging
from datetime import datetime, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import event
from middleware.auth import min_role_required
from models.sensor import Sensor, is_temperature_sensor
from models.sensor_reading import SensorReading
from models.rule_condition import RuleCondition
from services.esphome_generator import OPPOSITE_STATE
from models.controller_pin import ControllerPin
from models.controller import Controller
from services import cleanup
from services.pins import claim_pin, ensure_not_i2c_pin, ensure_not_pwm_module_pin, get_controller_pin, release_pin_if_unused
from schemas.sensor import SensorRead, SensorCreate, SensorUpdate, SensorListResponse
from middleware.database import get_db
from services.tools import notify_controller_update, validate_entity_name_uniqueness
from services import technical_names

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sensors", tags=["sensors"], dependencies=[Depends(min_role_required("consult"))])


# Fonction utilitaire pour générer un nom technique propre si non fourni

# ESP32 : GPIO 34 à 39 sont en entrée seule, incompatibles avec le 1-Wire
# (bus bidirectionnel) ; un module d'extension (PCF8574...) ne convient pas non plus.
ESP32_INPUT_ONLY_PINS = range(34, 40)


def _validate_one_wire_pin(db: Session, pin_id: int) -> None:
    pin = db.query(ControllerPin).filter(ControllerPin.id == pin_id).first()
    if not pin:
        raise HTTPException(status_code=404, detail="Broche introuvable.")
    if pin.module_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Une sonde de température 1-Wire doit être branchée sur une broche de l'ESP, pas d'un module d'extension.",
        )
    if pin.pin_number.isdigit() and int(pin.pin_number) in ESP32_INPUT_ONLY_PINS:
        raise HTTPException(
            status_code=400,
            detail=f"GPIO {pin.pin_number} est en entrée seule sur l'ESP32 : incompatible avec une sonde 1-Wire (utiliser par ex. GPIO 4).",
        )


def _validate_sensor_pin(
    db: Session,
    pin_id: int,
    is_temperature: bool,
    address: str | None,
    exclude_sensor_id: int | None = None,
) -> None:
    """
    Plus de contrainte unique (controller_id, pin_id) au niveau DB (retirée
    du modèle) : un bus 1-Wire porte plusieurs sondes température sur la
    même broche, distinguées par leur adresse. Toute autre combinaison
    (broche déjà occupée par un capteur non-température, ou un nouveau
    capteur non-température sur une broche déjà occupée) reste interdite,
    comme avant.
    """
    pin = db.query(ControllerPin).filter(ControllerPin.id == pin_id).first()
    if pin is not None:
        ensure_not_i2c_pin(pin)
        ensure_not_pwm_module_pin(pin)
    if is_temperature:
        _validate_one_wire_pin(db, pin_id)

    query = db.query(Sensor).filter(Sensor.pin_id == pin_id)
    if exclude_sensor_id is not None:
        query = query.filter(Sensor.id != exclude_sensor_id)
    existing = query.all()

    if not existing:
        return

    if not is_temperature or any(s.unit != "°C" for s in existing):
        raise HTTPException(status_code=409, detail="Cette broche est déjà utilisée par un autre capteur.")

    # Plusieurs sondes sur une broche : chacune doit avoir son adresse. Sans adresse,
    # le firmware prend la n-ième sonde trouvée, qui peut être celle d'un autre bac.
    if not address:
        raise HTTPException(
            status_code=409,
            detail=(
                "Une autre sonde utilise déjà cette broche : choisis l'adresse de cette sonde "
                "(bouton Rechercher), ou branche-la sur une autre broche."
            ),
        )
    if any(s.address == address for s in existing):
        raise HTTPException(status_code=409, detail="Cette adresse 1-Wire est déjà utilisée sur cette broche.")
    unaddressed = [s.name for s in existing if not s.address]
    if unaddressed:
        raise HTTPException(
            status_code=409,
            detail=f"Renseigne d'abord l'adresse de la sonde « {unaddressed[0]} », déjà sur cette broche.",
        )


@router.post(
    "/",
    response_model=SensorRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user"))],
)
def create_sensor(sensor: SensorCreate, db: Session = Depends(get_db)):
    try:
        # 0. Nom unique dans l'aquarium (capteurs et équipements confondus)
        validate_entity_name_uniqueness(db=db, name=sensor.name, entity_type="sensor", aquarium_id=sensor.aquarium_id)
        if sensor.unit is None:
            raise HTTPException(status_code=400, detail="Précise la mesure du capteur : température ou niveau.")
        get_controller_pin(db, sensor.pin_id, sensor.controller_id)
        # unit est normalisée par le schéma : "°C" (sonde 1-Wire) ou "level" (flotteur)
        is_temperature = sensor.unit == "°C"
        _validate_sensor_pin(db, sensor.pin_id, is_temperature, sensor.address)

        # Gestion ou auto-génération du technical_name s'il n'est pas explicitement passé
        # Nom technique (MQTT, firmware) unique partout : suffixé si déjà pris
        explicit = getattr(sensor, "technical_name", None)
        tech_name = (
            technical_names.unique_technical_name(db, technical_names.slugify(explicit), "sensor")
            if explicit
            else technical_names.technical_name_for(db, sensor.name, sensor.aquarium_id, "sensor")
        )

        sensor_data = sensor.model_dump()
        sensor_data["type"] = "sensor" if is_temperature else "binary_sensor"
        sensor_data["technical_name"] = tech_name

        db_sensor = Sensor(**sensor_data)
        db.add(db_sensor)

        # On marque le contrôleur comme à mettre à jour (is_dirty)
        controller = db.query(Controller).filter(Controller.id == db_sensor.controller_id).first()
        if controller:
            controller.is_dirty = True

        db.commit()
        db.refresh(db_sensor)

        # Prévient l'ESP qu'il y a un nouvel équipement
        notify_controller_update(controller_id=db_sensor.controller_id, db=db)

        return db_sensor
    except HTTPException:
        # Laisse passer les erreurs de validation (400, 404, etc.) sans les transformer en 500
        raise
    except Exception:
        logger.exception("Erreur lors de l'ajout d'un capteur")
        raise


@event.listens_for(Sensor, "after_insert")
def update_pin(mapper, connection, target):
    # On adapte le bus/mode selon le type de capteur
    bus_type = "GPIO"
    mode_type = "IN"
    if is_temperature_sensor(target):
        bus_type = "1WIRE"
        mode_type = "SENSOR"
    elif target.type == "niveau":
        bus_type = "GPIO"
        mode_type = "IN"

    connection.execute(
        ControllerPin.__table__.update()
        .where(ControllerPin.id == target.pin_id)
        .values(
            bus=bus_type,
            mode=mode_type,
            label=target.name  # On garde le joli nom pour le libellé physique de la pin
        )
    )


@router.patch(
    "/{sensor_id}",
    response_model=SensorRead,
    dependencies=[Depends(min_role_required("user"))],
)
def update_sensor(sensor_id: int, update_data: SensorUpdate, db: Session = Depends(get_db)):
    try:
        sensor = db.query(Sensor).filter(Sensor.id == sensor_id).first()
        if not sensor:
            raise HTTPException(status_code=404, detail="Capteur non trouvé")

        update_dict = update_data.model_dump(exclude_unset=True)
        # Champs gérés par l'API ou le contrôleur, pas par le formulaire
        for field in ("created_at", "last_value", "technical_name"):
            update_dict.pop(field, None)

        name_changed = "name" in update_dict and update_dict["name"] != sensor.name
        if name_changed or update_dict.get("aquarium_id", sensor.aquarium_id) != sensor.aquarium_id:
            validate_entity_name_uniqueness(
                db=db,
                name=update_dict.get("name", sensor.name),
                entity_type="sensor",
                aquarium_id=update_dict.get("aquarium_id", sensor.aquarium_id),
                entity_id=sensor.id,
            )

        effective_unit = update_dict.get("unit", sensor.unit)
        is_temperature = str(effective_unit or "").lower() in ("°c", "temperature")
        if "unit" in update_dict:
            update_dict["type"] = "sensor" if is_temperature else "binary_sensor"

        # Inversion changée : l'affichage (et donc le sens des règles) bascule.
        # On convertit les conditions de ce capteur pour que le comportement
        # physique ne change pas (ex : « couper l'osmolateur quand c'est plein »).
        if "is_inverted" in update_dict and bool(update_dict["is_inverted"]) != bool(sensor.is_inverted):
            for condition in db.query(RuleCondition).filter(RuleCondition.sensor_id == sensor.id):
                if condition.trigger_state:
                    flipped = OPPOSITE_STATE.get(condition.trigger_state.upper())
                    if flipped:
                        condition.trigger_state = flipped

        old_controller_id, old_pin_id = sensor.controller_id, sensor.pin_id
        new_controller_id = update_dict.get("controller_id", old_controller_id)
        new_pin_id = update_dict.get("pin_id", old_pin_id)
        wiring_changed = new_controller_id != old_controller_id or new_pin_id != old_pin_id
        new_pin = get_controller_pin(db, new_pin_id, new_controller_id) if wiring_changed else None

        if wiring_changed or "unit" in update_dict or "address" in update_dict:
            _validate_sensor_pin(
                db,
                new_pin_id,
                is_temperature,
                update_dict.get("address", sensor.address),
                exclude_sensor_id=sensor.id,
            )

        updated = False
        for field, value in update_dict.items():
            if getattr(sensor, field) != value:
                setattr(sensor, field, value)
                updated = True
        # Nom ou aquarium changé : nom technique recalculé (firmware à reflasher)
        if technical_names.rename(db, sensor, "sensor"):
            updated = True

        if wiring_changed:
            db.flush()
            release_pin_if_unused(db, old_pin_id, exclude_sensor_id=sensor.id)
            claim_pin(new_pin, "1WIRE" if is_temperature else "GPIO", "SENSOR" if is_temperature else "IN", sensor.name)
        elif "name" in update_dict and sensor.pin is not None:
            sensor.pin.label = sensor.name

        if updated:
            for controller_id in {old_controller_id, sensor.controller_id}:
                controller = db.query(Controller).filter(Controller.id == controller_id).first()
                if controller:
                    controller.is_dirty = True
            db.commit()
            db.refresh(sensor)

        return sensor
    except HTTPException:
        raise
    except Exception:
        logger.exception("Erreur lors de la mise à jour du capteur")
        raise


@router.delete(
    "/{sensor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("manager"))],
)
def delete_sensor(sensor_id: int, db: Session = Depends(get_db)):
    try:
        sensor = db.query(Sensor).filter(Sensor.id == sensor_id).first()
        if not sensor:
            raise HTTPException(status_code=404, detail="Capteur non trouvé")

        cleanup.delete_sensor(db, sensor)
        db.commit()
        return
    except HTTPException:
        raise
    except Exception:
        logger.exception("Erreur lors de la suppression du capteur")
        raise


# Période -> (durée, taille d'un regroupement en secondes) : ~300 points par graphique
HISTORY_PERIODS = {
    "24h": (timedelta(hours=24), 300),
    "7d": (timedelta(days=7), 1800),
    "30d": (timedelta(days=30), 7200),
    "90d": (timedelta(days=90), 21600),
}


@router.get("/{sensor_id}/history")
def get_sensor_history(
    sensor_id: int,
    period: Literal["24h", "7d", "30d", "90d"] = Query("24h", description="Période affichée"),
    db: Session = Depends(get_db),
):
    """
    Historique d'un capteur regroupé par intervalles (moyenne, minimum,
    maximum et dernière valeur de chaque intervalle) pour les graphiques.
    """
    sensor = db.query(Sensor).filter(Sensor.id == sensor_id).first()
    if not sensor:
        raise HTTPException(status_code=404, detail="Capteur non trouvé")

    span, bucket_seconds = HISTORY_PERIODS[period]
    end = datetime.now()
    start = end - span
    rows = (
        db.query(SensorReading.timestamp, SensorReading.value)
        .filter(SensorReading.sensor_id == sensor_id, SensorReading.timestamp >= start)
        .order_by(SensorReading.timestamp)
        .all()
    )

    buckets: dict[int, list[float]] = {}
    for timestamp, value in rows:
        key = int((timestamp - start).total_seconds()) // bucket_seconds
        buckets.setdefault(key, []).append(value)

    points = [
        {
            "t": start + timedelta(seconds=key * bucket_seconds),
            "avg": round(sum(values) / len(values), 3),
            "min": min(values),
            "max": max(values),
            "last": values[-1],
        }
        for key, values in sorted(buckets.items())
    ]
    values = [value for _, value in rows]
    return {
        "sensor_id": sensor.id,
        "period": period,
        "bucket_seconds": bucket_seconds,
        "unit": sensor.unit,
        "start": start,
        "end": end,
        "points": points,
        "stats": {
            "count": len(values),
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "avg": round(sum(values) / len(values), 3) if values else None,
        },
    }


@router.get("/{sensor_id}", response_model=SensorRead)
def get_sensor(sensor_id: int, db: Session = Depends(get_db)):
    try:
        sensor = db.query(Sensor).filter(Sensor.id == sensor_id).first()
        if not sensor:
            raise HTTPException(status_code=404, detail="Capteur non trouvé")
        return sensor
    except Exception:
        logger.exception("Erreur lors de la récupération du capteur")
        raise


@router.get("/", response_model=SensorListResponse)
def list_sensors(db: Session = Depends(get_db)):
    try:
        query_result = db.query(Sensor, ControllerPin)\
            .outerjoin(ControllerPin, Sensor.pin_id == ControllerPin.id)\
            .all()

        sensors_list = []
        for s, pin in query_result:
            sensor_data = SensorRead.model_validate(s).model_dump()

            if pin:
                sensor_data['pin_number'] = pin.pin_number
                sensor_data['module_id'] = pin.module_id
                sensor_data['module_number'] = pin.io_module.number if pin.io_module else None
            else:
                sensor_data['pin_number'] = "N/A"
                sensor_data['module_id'] = None

            sensors_list.append(sensor_data)

        return {"total": len(sensors_list), "sensors": sensors_list}
    except Exception:
        logger.exception("Erreur lors du listage des capteurs")
        raise