"""
Portée des tâches et articles de stock partagés entre aquariums.

- single   : l'aquarium de rattachement seul (aquarium_id)
- multiple : une sélection d'aquariums (table de liaison)
- all      : tous les aquariums, y compris ceux créés plus tard

aquarium_id reste toujours renseigné : c'est l'aquarium de rattachement
(celui depuis lequel l'élément a été créé), utilisé pour les alertes.
"""

from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from models.aquarium import Aquarium
from models.inventory import InventoryItem, inventory_item_aquariums
from models.maintenance_task import MaintenanceTask, maintenance_task_aquariums

SCOPES = ("single", "multiple", "all")

_LINKS = {
    InventoryItem: (inventory_item_aquariums, inventory_item_aquariums.c.item_id),
    MaintenanceTask: (maintenance_task_aquariums, maintenance_task_aquariums.c.task_id),
}


def concerns_aquarium(model, aquarium_id: int):
    """Condition SQL : l'élément concerne cet aquarium."""
    table, owner_column = _LINKS[model]
    linked = select(owner_column).where(table.c.aquarium_id == aquarium_id)
    return or_(
        model.scope == "all",
        (model.scope == "single") & (model.aquarium_id == aquarium_id),
        (model.scope == "multiple") & model.id.in_(linked),
    )


def concerned_ids(item, all_ids: Iterable[int]) -> list[int]:
    return list(all_ids) if item.scope == "all" else item.aquarium_ids


def scope_label(item, names: dict[int, str]) -> str:
    """« Bac récifal », « Bac A, Bac B » ou « Tous les aquariums »."""
    if item.scope == "all":
        return "Tous les aquariums"
    return ", ".join(names.get(i, "?") for i in item.aquarium_ids)


def apply_scope(db: Session, item, scope: str, aquarium_ids: Optional[list[int]], owner_id: int) -> None:
    """Règle la portée ; « multiple » avec un seul aquarium redevient « single »."""
    if scope not in SCOPES:
        raise HTTPException(status_code=400, detail="Portée inconnue.")
    if scope == "single" and aquarium_ids:
        scope = "multiple"  # un seul aquarium choisi : traité comme une sélection d'un bac
    if scope == "multiple":
        ids = sorted(set(aquarium_ids or []))
        aquariums = db.query(Aquarium).filter(Aquarium.id.in_(ids)).all() if ids else []
        if len(aquariums) != len(ids):
            raise HTTPException(status_code=400, detail="Aquarium inconnu dans la sélection.")
        if not aquariums:
            raise HTTPException(status_code=400, detail="Choisis au moins un aquarium.")
        if len(aquariums) == 1:
            item.scope, item.aquarium_id = "single", aquariums[0].id
            item.linked_aquariums = []
            return
        item.scope = "multiple"
        item.linked_aquariums = aquariums
        # Rattachement : l'aquarium d'origine s'il fait partie de la sélection
        item.aquarium_id = owner_id if owner_id in ids else ids[0]
        return
    item.scope = scope
    item.linked_aquariums = []
    item.aquarium_id = owner_id


def detach_aquarium(db: Session, aquarium_id: int) -> None:
    """
    Suppression d'un aquarium : ses éléments propres sont supprimés, les
    éléments partagés sont conservés et rattachés à un autre aquarium
    concerné (supprimés seulement s'il n'en reste aucun).
    """
    remaining = [a.id for a in db.query(Aquarium).filter(Aquarium.id != aquarium_id).order_by(Aquarium.id)]
    for model in (MaintenanceTask, InventoryItem):
        for item in db.query(model).filter(concerns_aquarium(model, aquarium_id)).all():
            if item.scope == "single":
                db.delete(item)
            elif item.scope == "all":
                if remaining:
                    item.aquarium_id = remaining[0] if item.aquarium_id == aquarium_id else item.aquarium_id
                else:
                    db.delete(item)
            else:
                others = [a for a in item.linked_aquariums if a.id != aquarium_id]
                if not others:
                    db.delete(item)
                elif len(others) == 1:
                    item.scope, item.aquarium_id, item.linked_aquariums = "single", others[0].id, []
                else:
                    item.linked_aquariums = others
                    if item.aquarium_id == aquarium_id:
                        item.aquarium_id = others[0].id
