"""
services/naming.py

Noms affichés uniques par aquarium (et non plus dans toute l'installation)
pour les lampes, règles et groupes d'équipements. Ces noms ne servent pas
d'identifiant dans le firmware (c'est l'id qui sert), l'assouplissement est
donc sans effet sur les contrôleurs.

Règles et groupes n'ont pas d'aquarium : on le déduit de leur cible
(équipement, membres du groupe, capteurs des conditions). Sans aquarium
déductible, ils forment un ensemble « global » à part.
"""

from typing import Iterable, Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.equipment import Equipment
from models.equipment_group import EquipmentGroup
from models.light import Light
from models.rule import Rule
from models.sensor import Sensor


def _conflict(what: str, name: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{what} porte déjà le nom « {name} » dans cet aquarium.")


def _overlap(a: set[int], b: set[int]) -> bool:
    return bool(a & b) or (not a and not b)


def ensure_unique_light_name(db: Session, name: str, aquarium_id: int, light_id: Optional[int] = None) -> None:
    query = db.query(Light).filter(func.lower(Light.name) == name.strip().lower(), Light.aquarium_id == aquarium_id)
    if light_id is not None:
        query = query.filter(Light.id != light_id)
    if query.first():
        raise _conflict("Une lampe", name)


def group_aquariums(equipments: Iterable[Equipment]) -> set[int]:
    return {e.aquarium_id for e in equipments if e.aquarium_id is not None}


def ensure_unique_group_name(db: Session, name: str, aquariums: set[int], group_id: Optional[int] = None) -> None:
    query = db.query(EquipmentGroup).filter(func.lower(EquipmentGroup.name) == name.strip().lower())
    if group_id is not None:
        query = query.filter(EquipmentGroup.id != group_id)
    for other in query:
        if _overlap(aquariums, group_aquariums(other.equipments)):
            raise _conflict("Un groupe", name)


def rule_aquariums(
    db: Session, equipment_id: Optional[int], group_id: Optional[int], sensor_ids: Iterable[Optional[int]]
) -> set[int]:
    if equipment_id is not None:
        equipment = db.get(Equipment, equipment_id)
        return {equipment.aquarium_id} if equipment else set()
    if group_id is not None:
        group = db.get(EquipmentGroup, group_id)
        return group_aquariums(group.equipments) if group else set()
    ids = [i for i in sensor_ids if i is not None]
    if not ids:
        return set()
    return {aq for (aq,) in db.query(Sensor.aquarium_id).filter(Sensor.id.in_(ids))}


def ensure_unique_rule_name(db: Session, name: str, aquariums: set[int], rule_id: Optional[int] = None) -> None:
    query = db.query(Rule).filter(func.lower(Rule.name) == name.strip().lower())
    if rule_id is not None:
        query = query.filter(Rule.id != rule_id)
    for other in query:
        others = rule_aquariums(db, other.equipment_id, other.group_id, [c.sensor_id for c in other.conditions])
        if _overlap(aquariums, others):
            raise _conflict("Une règle", name)
