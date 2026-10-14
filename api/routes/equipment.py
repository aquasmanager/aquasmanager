"""
Équipements : création (broche, relais), modification, commande (marche/arrêt,
mode), défauts et historique des activations.
"""

from datetime import datetime, timezone
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import event

from drivers.mqtt import mqtt_driver
from services import tools
from middleware.auth import min_role_required
from models.equipment import Equipment
from models.equipment_activation import EquipmentActivation
from models.controller import Controller
from models.controller_pin import ControllerPin
from schemas.equipment import EquipmentModeUpdate, EquipmentRead, EquipmentCreate, EquipmentStatusUpdate, EquipmentUpdate, EquipmentListResponse
from schemas.equipment_activation import EquipmentActivationRead
from middleware.database import get_db
from services import cleanup
from services.pins import claim_pin, ensure_pin_free_for_equipment, get_controller_pin, release_pin_if_unused
from services.tools import notify_controller_update, validate_entity_name_uniqueness
from services import technical_names

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/equipments", tags=["equipments"], dependencies=[Depends(min_role_required("consult"))])


# Fonction utilitaire pour générer un nom technique propre

@router.post(
    "/",
    response_model=EquipmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user"))],
)
def create_equipment(equipment: EquipmentCreate, db: Session = Depends(get_db)):
    try:
        # 0. Nom unique dans l'aquarium (capteurs et équipements confondus)
        validate_entity_name_uniqueness(db=db, name=equipment.name, entity_type="equipment", aquarium_id=equipment.aquarium_id)

        # 1. Enregistrement en base de données
        controller = db.query(Controller).filter(Controller.id == equipment.controller_id).first()
        if not controller:
            raise HTTPException(status_code=404, detail="Le contrôleur n'existe pas")

        pin = get_controller_pin(db, equipment.pin_id, equipment.controller_id)
        ensure_pin_free_for_equipment(db, pin)

        # Gestion ou auto-génération du technical_name s'il n'est pas fourni
        equipment_data = equipment.model_dump()
        # Nom technique (MQTT, firmware) « <nom>_<aquarium> », unique partout
        equipment_data["technical_name"] = (
            technical_names.unique_technical_name(db, technical_names.slugify(equipment_data["technical_name"]), "equipment")
            if equipment_data.get("technical_name")
            else technical_names.technical_name_for(db, equipment_data["name"], equipment_data["aquarium_id"], "equipment")
        )
        if equipment_data.get("inverted") is None:
            equipment_data["inverted"] = tools.calculate_inversion(
                relay_type="ACTIVE_HIGH", physical_contact=equipment.physical_contact.value
            )

        db_equipment = Equipment(**equipment_data)
        db.add(db_equipment)

        # On marque le contrôleur comme à mettre à jour (is_dirty)
        controller.is_dirty = True

        db.commit()
        db.refresh(db_equipment)

        # 2. Prévient l'ESP qu'il y a un nouvel équipement
        notify_controller_update(controller_id=db_equipment.controller_id, db=db)

        return db_equipment
    except HTTPException:
        # On laisse passer les HTTPException (comme le 400 de doublon ou le 404) sans les catcher dans le bloc générique
        raise
    except Exception:
        logger.exception("Erreur lors de l'ajout d'un équipement")
        raise


@event.listens_for(Equipment, "after_insert")
def update_pin(mapper, connection, target):
    connection.execute(
        ControllerPin.__table__.update()
        .where(ControllerPin.id == target.pin_id)
        .values(
            bus="GPIO",
            mode="OUT",
            label=target.name  # On garde le joli nom pour le libellé physique
        )
    )


@router.patch(
    "/{equipment_id}",
    response_model=EquipmentRead,
    dependencies=[Depends(min_role_required("user"))],
)
def update_equipment(equipment_id: int, update_data: EquipmentUpdate, db: Session = Depends(get_db)):
    try:
        # 1. On met à jour la base de données
        equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
        if not equipment:
            raise HTTPException(status_code=404, detail="Équipement non trouvé")

        update_dict = update_data.model_dump(exclude_unset=True)
        # Champs gérés par le contrôleur ou l'API, pas par le formulaire
        for field in ("created_at", "status", "technical_name"):
            update_dict.pop(field, None)

        name_changed = "name" in update_dict and update_dict["name"] != equipment.name
        if name_changed or update_dict.get("aquarium_id", equipment.aquarium_id) != equipment.aquarium_id:
            validate_entity_name_uniqueness(
                db=db,
                name=update_dict.get("name", equipment.name),
                entity_type="equipment",
                aquarium_id=update_dict.get("aquarium_id", equipment.aquarium_id),
                entity_id=equipment.id,
            )

        old_controller_id, old_pin_id = equipment.controller_id, equipment.pin_id
        new_controller_id = update_dict.get("controller_id", old_controller_id)
        new_pin_id = update_dict.get("pin_id", old_pin_id)
        wiring_changed = new_controller_id != old_controller_id or new_pin_id != old_pin_id
        if wiring_changed:
            new_pin = get_controller_pin(db, new_pin_id, new_controller_id)
            ensure_pin_free_for_equipment(db, new_pin, equipment_id=equipment.id)

        updated = False
        for field, value in update_dict.items():
            if getattr(equipment, field) != value:
                setattr(equipment, field, value)
                updated = True
        # Nom ou aquarium changé : nom technique recalculé (firmware à reflasher)
        if technical_names.rename(db, equipment, "equipment"):
            updated = True

        if wiring_changed:
            db.flush()
            release_pin_if_unused(db, old_pin_id, exclude_equipment_id=equipment.id)
            claim_pin(new_pin, "GPIO", "OUT", equipment.name)
        elif "name" in update_dict and equipment.pin is not None:
            equipment.pin.label = equipment.name

        if updated:
            # Les contrôleurs concernés doivent être reflashés
            for controller_id in {old_controller_id, equipment.controller_id}:
                controller = db.query(Controller).filter(Controller.id == controller_id).first()
                if controller:
                    controller.is_dirty = True
            db.commit()
            db.refresh(equipment)

            # 2. On met à jour l'ESP
            notify_controller_update(controller_id=equipment.controller_id, db=db)

        return equipment
    except HTTPException:
        raise
    except Exception:
        logger.exception("Erreur lors de la mise à jour de l'équipement")
        raise


@router.post("/{equipment_id}/fault/clear", dependencies=[Depends(min_role_required("user"))])
def clear_equipment_fault(equipment_id: int, db: Session = Depends(get_db)):
    """
    Acquitte le verrou d'anomalie (LEVEL_TIMEOUT / TOO_MANY_CYCLES) d'un
    osmolateur : republie sur le topic .../fault/clear pour que l'ESP lève
    fault_latched_<eq>. La résolution en base des alertes ouvertes est
    confirmée par le retour MQTT fault=OK (voir drivers/mqtt.py), pas de
    façon optimiste ici.
    """
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise HTTPException(status_code=404, detail="Équipement non trouvé")

    controller = db.query(Controller).filter(Controller.id == equipment.controller_id).first()
    if not controller:
        raise HTTPException(status_code=404, detail="Contrôleur introuvable")

    topic = f"{controller.technical_name}/switch/{technical_names.firmware_name(equipment)}/fault/clear"
    mqtt_driver.publish(topic, "CLEAR")
    logger.info(
        "Reset défaut demandé pour %s (%s) -> publish %s/%s",
        equipment.technical_name, equipment.id, mqtt_driver.topic_prefix, topic,
    )

    return {"detail": "Demande de réinitialisation envoyée à l'équipement."}


@router.delete(
    "/{equipment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("manager"))],
)
def delete_equipment(equipment_id: int, db: Session = Depends(get_db)):
    try:
        # 1. On supprime l'équipement de la base
        equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
        if not equipment:
            raise HTTPException(status_code=404, detail="Équipement non trouvé")

        controller_id = equipment.controller_id
        cleanup.delete_equipment(db, equipment)
        db.commit()

        # 2. On met à jour l'ESP
        notify_controller_update(controller_id=controller_id, db=db)

        return
    except HTTPException:
        raise
    except Exception:
        logger.exception("Erreur lors de la suppression de l'équipement")
        raise


@router.get("/{equipment_id}", response_model=EquipmentRead)
def get_equipment(equipment_id: int, db: Session = Depends(get_db)):
    try:
        equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
        if not equipment:
            raise HTTPException(status_code=404, detail="Équipement non trouvé")
        return equipment
    except Exception:
        logger.exception("Erreur lors de la récupération de l'équipement")
        raise


@router.get("/{equipment_id}/activations", response_model=List[EquipmentActivationRead])
def list_equipment_activations(
    equipment_id: int,
    limit: int = Query(20, ge=1, le=5000),
    since: Optional[datetime] = Query(None, description="Seulement les activations commencées depuis cette date"),
    db: Session = Depends(get_db),
):
    """
    Historique des activations (début/fin/durée) de l'équipement, les plus
    récentes en premier. Utilisé par les cartes du tableau de bord (osmolateur,
    équipement) et leur vue agrandie sur une période.
    """
    query = db.query(EquipmentActivation).filter(
        EquipmentActivation.equipment_id == equipment_id, EquipmentActivation.ended_at.isnot(None)
    )
    if since is not None:
        # Dates stockées en UTC naïf
        if since.tzinfo is not None:
            since = since.astimezone(timezone.utc).replace(tzinfo=None)
        query = query.filter(EquipmentActivation.started_at >= since)
    return query.order_by(EquipmentActivation.started_at.desc()).limit(limit).all()


@router.get("/", response_model=EquipmentListResponse)
def list_equipments(db: Session = Depends(get_db)):
    try:
        equipments = db.query(Equipment).all()
        total = len(equipments)
        return {"total": total, "equipments": equipments}
    except Exception:
        logger.exception("Erreur lors du listage des équipements")
        raise


@router.post("/{equipment_id}/toggle", dependencies=[Depends(min_role_required("user"))])
def set_equipment_status(equipment_id: int, payload: EquipmentStatusUpdate, db: Session = Depends(get_db)):
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise HTTPException(status_code=404, detail="Équipement non trouvé")

    controller = db.query(Controller).filter(Controller.id == equipment.controller_id).first()
    if controller:
        topic = f"{controller.technical_name}/switch/{technical_names.firmware_name(equipment)}/command"

        # On publie la valeur 100% nettoyée
        mqtt_driver.publish(topic, payload.status, qos=1)

    return {"status": "success", "state": payload.status}

@router.patch(
    "/{equipment_id}/mode",
    response_model=EquipmentRead,
    dependencies=[Depends(min_role_required("user"))],
)
def update_equipment_mode(equipment_id: int, payload: EquipmentModeUpdate, db: Session = Depends(get_db)):
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise HTTPException(status_code=404, detail="Équipement non trouvé")

    # 1. Mise à jour de la volonté humaine en base
    equipment.mode = payload.mode  # 'AUTO', 'ON', 'OFF'
    db.commit()
    db.refresh(equipment)

    # 2. Publication de la consigne sur MQTT pour l'ESP32
    controller = db.query(Controller).filter(Controller.id == equipment.controller_id).first()
    if controller:
        # On extrait proprement la valeur de l'Enum (ex: "AUTO", "ON", "OFF")
        mode_val = equipment.mode.value if hasattr(equipment.mode, "value") else str(equipment.mode)

        # On utilise le même format de topic que celui généré dans ESPHome :
        # aquarium/{controller_technical_name}/equipment/{equipment.id}/mode
        topic = f"{controller.technical_name}/switch/{technical_names.firmware_name(equipment)}/mode/set"

        # L'ESP32 attend directement le texte brut (ex: "AUTO") car on fait `id(mode_test) = x;`
        mqtt_driver.publish(topic, mode_val, qos=1)

    return equipment