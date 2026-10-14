"""
Règles d'automatisation : validation, création, modification et suppression ;
marque les contrôleurs concernés « à reflasher » (les règles tournent sur l'ESP32).
"""

from typing import Set
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from models.equipment_group import EquipmentGroup
from models.rule import Rule
from models.rule_condition import RuleCondition
from models.equipment import Equipment
from models.sensor import Sensor, is_temperature_sensor
from models.controller import Controller
from schemas.rule import RuleCreate, RuleUpdate
from services.naming import ensure_unique_rule_name, rule_aquariums


def _get_impacted_controller_ids(db: Session, rule_in: RuleCreate | RuleUpdate | Rule) -> Set[int]:
    """
    Identifie tous les controller_id impactés par une règle (équipement cible,
    équipements d'un groupe cible, et capteurs impliqués dans les conditions).
    """
    controller_ids: Set[int] = set()

    # 1. Cible Équipement direct
    equipment_id = getattr(rule_in, "equipment_id", None)
    if equipment_id:
        equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
        if equipment and equipment.controller_id:
            controller_ids.add(equipment.controller_id)

    # 2. Cible Groupe d'équipements
    group_id = getattr(rule_in, "group_id", None)
    if group_id:
        group = db.query(EquipmentGroup).filter(EquipmentGroup.id == group_id).first()
        if group and hasattr(group, "equipments"):
            for eq in group.equipments:
                if eq.controller_id:
                    controller_ids.add(eq.controller_id)

    # 3. Capteurs liés aux conditions
    conditions = getattr(rule_in, "conditions", None)
    if conditions:
        for cond in conditions:
            # Compatibilité dictionnaire (depuis model_dump/update_data) ou objet Pydantic/ORMM
            sensor_id = cond.get("sensor_id") if isinstance(cond, dict) else getattr(cond, "sensor_id", None)
            if sensor_id:
                sensor = db.query(Sensor).filter(Sensor.id == sensor_id).first()
                if sensor and sensor.controller_id:
                    controller_ids.add(sensor.controller_id)

    return controller_ids


def _mark_controllers_dirty(db: Session, controller_ids: Set[int]) -> None:
    """
    Passe la colonne is_dirty à True pour la liste des identifiants de contrôleurs transmis.
    """
    if controller_ids:
        db.query(Controller).filter(Controller.id.in_(controller_ids)).update(
            {Controller.is_dirty: True}, synchronize_session=False
        )


def is_advanced_rule(rule) -> bool:
    """
    Règle gérée par le moteur de règles "avancé" du firmware (plusieurs
    conditions combinées ET/OU, un seuil numérique, une plage horaire, ou
    l'action inverse quand la condition cesse). Les autres règles à une seule
    condition d'état gardent le moteur historique.
    """
    conditions = list(getattr(rule, "conditions", None) or [])
    return (
        len(conditions) > 1
        or bool(getattr(rule, "revert_on_exit", False))
        or any(getattr(c, "condition_type", None) in ("THRESHOLD", "TIME_RANGE") for c in conditions)
    )


def _target_equipments(db: Session, equipment_id, group_id) -> list[Equipment]:
    if equipment_id is not None:
        return db.query(Equipment).filter(Equipment.id == equipment_id).all()
    if group_id is not None:
        group = db.query(EquipmentGroup).filter(EquipmentGroup.id == group_id).first()
        return list(group.equipments) if group else []
    return []


def validate_rule_definition(db: Session, *, action: str, equipment_id, group_id, conditions: list[dict]) -> None:
    """
    Les règles s'exécutent sur l'ESP : capteurs et équipements pilotés doivent
    être sur le même contrôleur, et chaque type de condition doit porter sur
    un capteur compatible.
    """
    sensors = []
    for cond in conditions:
        if cond["condition_type"] == "TIME_RANGE":
            continue
        sensor = db.query(Sensor).filter(Sensor.id == cond["sensor_id"]).first()
        if not sensor:
            raise HTTPException(status_code=404, detail=f"Le capteur {cond['sensor_id']} n'existe pas")
        numeric = is_temperature_sensor(sensor)
        if cond["condition_type"] == "THRESHOLD" and not numeric:
            raise HTTPException(
                status_code=400,
                detail=f"« {sensor.name} » n'est pas un capteur numérique : utilise une condition d'état.",
            )
        if cond["condition_type"] == "SENSOR_STATE" and numeric:
            raise HTTPException(
                status_code=400,
                detail=f"« {sensor.name} » est une sonde de température : utilise une condition de seuil.",
            )
        sensors.append(sensor)

    controller_ids = {s.controller_id for s in sensors}
    if action != "NOTIFY":
        controller_ids |= {eq.controller_id for eq in _target_equipments(db, equipment_id, group_id)}
    if len(controller_ids) > 1:
        raise HTTPException(
            status_code=400,
            detail="Les capteurs et les équipements d'une règle doivent être branchés sur le même contrôleur "
                   "(la règle s'exécute directement sur l'ESP).",
        )

    if any(cond["condition_type"] == "TIME_RANGE" for cond in conditions):
        if not controller_ids:
            raise HTTPException(
                status_code=400,
                detail="Une règle horaire doit piloter un équipement ou porter aussi sur un capteur.",
            )
        controller = db.query(Controller).filter(Controller.id == next(iter(controller_ids))).first()
        if controller is None or not controller.rtc_model:
            raise HTTPException(
                status_code=400,
                detail="Plage horaire impossible : ajoute d'abord une horloge RTC au contrôleur "
                       "(Contrôleurs > Modules d'extension).",
            )


def create_rule_service(db: Session, rule_in: RuleCreate) -> Rule:
    """
    Crée une nouvelle règle d'automatisation avec ses conditions associées.
    """
    # 1. Vérifier la cible (soit equipment_id, soit group_id)
    if rule_in.equipment_id is not None:
        equipment = db.query(Equipment).filter(Equipment.id == rule_in.equipment_id).first()
        if not equipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="L'équipement cible n'existe pas"
            )
    elif rule_in.group_id is not None:
        group = db.query(EquipmentGroup).filter(EquipmentGroup.id == rule_in.group_id).first()
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Le groupe d'équipements cible n'existe pas"
            )
    elif str(rule_in.action or "").upper() != "NOTIFY":
        # Une règle NOTIFY pure (ex: notification sur un capteur, sans
        # piloter d'équipement) n'a pas besoin de cible.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La règle doit cibler soit un équipement, soit un groupe d'équipements."
        )

    # 2. Valider l'existence de chaque capteur utilisé dans les conditions
    for condition in rule_in.conditions:
        if condition.sensor_id is not None:
            sensor = db.query(Sensor).filter(Sensor.id == condition.sensor_id).first()
            if not sensor:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Le capteur avec l'ID {condition.sensor_id} n'existe pas"
                )

    validate_rule_definition(
        db,
        action=rule_in.action,
        equipment_id=rule_in.equipment_id,
        group_id=rule_in.group_id,
        conditions=[c.model_dump() for c in rule_in.conditions],
    )

    ensure_unique_rule_name(
        db, rule_in.name,
        rule_aquariums(db, rule_in.equipment_id, rule_in.group_id, [c.sensor_id for c in rule_in.conditions]),
    )

    # 3. Création de la règle
    rule_data = rule_in.model_dump(exclude={"conditions"})
    db_rule = Rule(**rule_data)
    db.add(db_rule)
    db.flush()

    # 4. Création des conditions associées
    for condition_in in rule_in.conditions:
        db_condition = RuleCondition(
            rule_id=db_rule.id,
            **condition_in.model_dump()
        )
        db.add(db_condition)

    # 5. Marquer les contrôleurs impactés comme "dirty"
    impacted_controllers = _get_impacted_controller_ids(db, rule_in)
    _mark_controllers_dirty(db, impacted_controllers)

    db.commit()
    db.refresh(db_rule)

    return db_rule


def update_rule_service(db: Session, rule_id: int, rule_in: RuleUpdate) -> Rule:
    """
    Met à jour une règle existante et marque les contrôleurs concernés comme "dirty".
    """
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Règle non trouvée")

    # Récupérer les contrôleurs impactés AVANT modification
    old_controller_ids = _get_impacted_controller_ids(db, rule)

    update_data = rule_in.model_dump(exclude_unset=True)

    # 1. Gestion du changement de cible (Équipement <-> Groupe)
    if "equipment_id" in update_data:
        eq_id = update_data["equipment_id"]
        if eq_id is not None:
            equipment = db.query(Equipment).filter(Equipment.id == eq_id).first()
            if not equipment:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="L'équipement cible n'existe pas")
            rule.group_id = None
        rule.equipment_id = eq_id

    if "group_id" in update_data:
        grp_id = update_data["group_id"]
        if grp_id is not None:
            group = db.query(EquipmentGroup).filter(EquipmentGroup.id == grp_id).first()
            if not group:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Le groupe d'équipements n'existe pas")
            rule.equipment_id = None
        rule.group_id = grp_id

    # 2. Gestion des conditions si elles sont fournies dans le patch
    if "conditions" in update_data:
        for cond_in in update_data["conditions"]:
            if cond_in.get("sensor_id") is not None:
                sensor = db.query(Sensor).filter(Sensor.id == cond_in["sensor_id"]).first()
                if not sensor:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Le capteur {cond_in['sensor_id']} n'existe pas"
                    )

        rule.conditions.clear()
        for cond_in in update_data["conditions"]:
            rule.conditions.append(RuleCondition(**cond_in))

        update_data.pop("conditions")

    # 3. Mise à jour des autres champs simples
    for field, value in update_data.items():
        if field not in ("equipment_id", "group_id"):
            setattr(rule, field, value)

    db.flush()
    ensure_unique_rule_name(
        db, rule.name, rule_aquariums(db, rule.equipment_id, rule.group_id, [c.sensor_id for c in rule.conditions]), rule.id
    )
    validate_rule_definition(
        db,
        action=rule.action,
        equipment_id=rule.equipment_id,
        group_id=rule.group_id,
        conditions=[
            {"sensor_id": c.sensor_id, "condition_type": c.condition_type} for c in rule.conditions
        ],
    )

    # 4. Marquer à la fois les anciens et les nouveaux contrôleurs impactés comme dirty
    new_controller_ids = _get_impacted_controller_ids(db, rule)
    _mark_controllers_dirty(db, old_controller_ids | new_controller_ids)

    db.commit()
    db.refresh(rule)
    return rule


def delete_rule_service(db: Session, rule_id: int) -> bool:
    """
    Supprime une règle par son ID et marque les contrôleurs associés comme "dirty".
    """
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"La règle avec l'ID {rule_id} n'existe pas"
        )

    # Identifier les contrôleurs rattachés avant suppression
    impacted_controllers = _get_impacted_controller_ids(db, rule)

    db.delete(rule)

    # Marquer comme dirty
    _mark_controllers_dirty(db, impacted_controllers)

    db.commit()
    return True