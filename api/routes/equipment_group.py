"""
Groupes d'équipements : création, modification et commande groupée
(marche/arrêt, mode) de plusieurs équipements d'un coup.
"""

from fastapi import APIRouter, Depends, HTTPException
from services import technical_names
from sqlalchemy.orm import Session
from typing import List
from drivers.mqtt import mqtt_driver
from middleware.auth import min_role_required
from middleware.database import get_db
from models.equipment_group import EquipmentGroup
from models.equipment import Equipment
from schemas.equipment_group import (
    EquipmentGroupCreate,
    EquipmentGroupUpdate,
    EquipmentGroupResponse,
    GroupCommandPayload,
    GroupControlModeRequest
)

from services.naming import ensure_unique_group_name, group_aquariums

router = APIRouter(prefix="/equipment-groups", tags=["Equipment Groups"], dependencies=[Depends(min_role_required("consult"))])

# 1. Créer un groupe d'équipements
@router.post(
    "/",
    response_model=EquipmentGroupResponse,
    dependencies=[Depends(min_role_required("user"))],
)
def create_equipment_group(data: EquipmentGroupCreate, db: Session = Depends(get_db)):
    equipments = db.query(Equipment).filter(Equipment.id.in_(data.equipment_ids)).all() if data.equipment_ids else []
    ensure_unique_group_name(db, data.name, group_aquariums(equipments))
    new_group = EquipmentGroup(name=data.name)
    new_group.equipments = equipments

    db.add(new_group)
    db.commit()
    db.refresh(new_group)
    return new_group

# 2. Lister tous les groupes
@router.get("/", response_model=List[EquipmentGroupResponse])
def get_equipment_groups(db: Session = Depends(get_db)):
    return db.query(EquipmentGroup).all()

# 3. Récupérer un groupe spécifique
@router.get("/{group_id}", response_model=EquipmentGroupResponse)
def get_equipment_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(EquipmentGroup).filter(EquipmentGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Groupe introuvable")
    return group

# 4. Mettre à jour un groupe (nom ou équipements associés)
@router.put(
    "/{group_id}",
    response_model=EquipmentGroupResponse,
    dependencies=[Depends(min_role_required("user"))],
)
def update_equipment_group(group_id: int, data: EquipmentGroupUpdate, db: Session = Depends(get_db)):
    group = db.query(EquipmentGroup).filter(EquipmentGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Groupe introuvable")

    equipments = (
        db.query(Equipment).filter(Equipment.id.in_(data.equipment_ids)).all()
        if data.equipment_ids is not None
        else list(group.equipments)
    )
    ensure_unique_group_name(db, data.name if data.name is not None else group.name, group_aquariums(equipments), group.id)
    if data.name is not None:
        group.name = data.name
    if data.equipment_ids is not None:
        group.equipments = equipments

    db.commit()
    db.refresh(group)
    return group

# 5. Supprimer un groupe
@router.delete("/{group_id}", dependencies=[Depends(min_role_required("manager"))])
def delete_equipment_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(EquipmentGroup).filter(EquipmentGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Groupe introuvable")

    db.delete(group)
    db.commit()
    return {"message": f"Groupe {group.name} supprimé avec succès"}

# 6. Action globale sur le groupe (Ex: Couper le RAC et l'écumeur d'un coup)
@router.post("/{group_id}/toggle", dependencies=[Depends(min_role_required("user"))])
def control_equipment_group(group_id: int, payload: GroupCommandPayload, db: Session = Depends(get_db)):
    group = db.query(EquipmentGroup).filter(EquipmentGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Groupe non trouvé")

    action = payload.command.upper() # Normalisation en majuscules (ex: "OFF" ou "ON")

    for equipment in group.equipments:
        # 1. Mettre à jour l'état dans la BDD
        equipment.status = action

        # 2. Récupération des noms techniques
        controller_tech_name = getattr(equipment.controller, "technical_name", "aquarium")
        equipment_tech_name = technical_names.firmware_name(equipment)

        # 3. Construction du topic et du payload
        topic = f"{mqtt_driver.topic_prefix}/{controller_tech_name}/switch/{equipment_tech_name}/command"

        # 4. Publication MQTT
        mqtt_driver.client.publish(topic, action, qos=1, retain=False)

    db.commit()
    return {"message": f"Groupe {action} avec succès"}


@router.post("/{group_id}/mode", dependencies=[Depends(min_role_required("user"))])
async def control_group_mode(
    group_id: int,
    payload: GroupControlModeRequest,
    db: Session = Depends(get_db)
):
    group = db.query(EquipmentGroup).filter(EquipmentGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Groupe d'équipements non trouvé")

    for equipment in group.equipments:
        controller_tech_name = getattr(equipment.controller, "technical_name", "aquarium")
        equipment_tech_name = technical_names.firmware_name(equipment)

        # On envoie l'ordre sur le topic de commande du mode
        topic = f"{controller_tech_name}/switch/{equipment_tech_name}/mode/set"
        mqtt_payload = payload.mode.value

        mqtt_driver.publish(topic, mqtt_payload, qos=1, retain=False)

    # Pas de db.commit() ici : c'est l'ESP qui confirmera l'application du mode via MQTT
    return {
        "message": f"Ordre de mode {payload.mode.value} envoyé au groupe {group.name}",
        "group_id": group_id,
        "mode": payload.mode.value
    }
