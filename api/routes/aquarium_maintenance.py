"""
aquarium_maintenance.py (routes)

Mode maintenance d'un aquarium (changement d'eau) : équipements choisis
arrêtés pour une durée, puis remis dans leur mode d'avant (services/maintenance.py).
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from middleware.auth import CARE_ROLES, min_role_required
from middleware.database import get_db
from models.aquarium import Aquarium
from models.equipment import Equipment
from services import maintenance

router = APIRouter(prefix="/aquariums", tags=["Maintenance"], dependencies=[Depends(min_role_required("consult"))])
# Changement d'eau : aussi pour le compte de gardiennage
CARE = [Depends(min_role_required("user", also=CARE_ROLES))]


class MaintenanceStart(BaseModel):
    equipment_ids: List[int] = Field(min_length=1, max_length=100)
    minutes: int = Field(ge=5, le=maintenance.MAX_MINUTES)


class MaintenanceEquipment(BaseModel):
    id: int
    name: str
    category: str
    mode: str
    status: str


class MaintenanceState(BaseModel):
    active: bool
    started_at: Optional[datetime] = None
    until: Optional[datetime] = None
    # Équipements arrêtés (maintenance en cours) ou dernière sélection
    equipment_ids: List[int]
    equipments: List[MaintenanceEquipment]


def _value(v) -> str:
    return v.value if hasattr(v, "value") else str(v)


def _state(db: Session, aquarium: Aquarium) -> dict:
    equipments = db.query(Equipment).filter(Equipment.aquarium_id == aquarium.id).order_by(Equipment.name).all()
    active = maintenance.is_active(aquarium)
    known = {e.id for e in equipments}
    selection = [i for i in (aquarium.maintenance_equipment_ids or []) if i in known]
    return {
        "active": active,
        "started_at": aquarium.maintenance_started_at if active else None,
        "until": aquarium.maintenance_until if active else None,
        # Première fois : tous les équipements de l'aquarium
        "equipment_ids": selection if aquarium.maintenance_equipment_ids is not None else sorted(known),
        "equipments": [
            {"id": e.id, "name": e.name, "category": _value(e.category), "mode": _value(e.mode), "status": _value(e.status)}
            for e in equipments
        ],
    }


def _aquarium(db: Session, aquarium_id: int) -> Aquarium:
    aquarium = db.get(Aquarium, aquarium_id)
    if aquarium is None:
        raise HTTPException(status_code=404, detail="Aquarium introuvable.")
    return aquarium


@router.get("/{aquarium_id}/maintenance", response_model=MaintenanceState)
def get_maintenance(aquarium_id: int, db: Session = Depends(get_db)):
    return _state(db, _aquarium(db, aquarium_id))


@router.post("/{aquarium_id}/maintenance", response_model=MaintenanceState, dependencies=CARE)
def start_maintenance(aquarium_id: int, payload: MaintenanceStart, db: Session = Depends(get_db)):
    """Démarre la maintenance, ou la modifie (équipements, durée) si elle est en cours."""
    aquarium = _aquarium(db, aquarium_id)
    try:
        maintenance.start(db, aquarium, payload.equipment_ids, payload.minutes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _state(db, aquarium)


@router.delete("/{aquarium_id}/maintenance", response_model=MaintenanceState, dependencies=CARE)
def stop_maintenance(aquarium_id: int, db: Session = Depends(get_db)):
    aquarium = _aquarium(db, aquarium_id)
    if maintenance.is_active(aquarium):
        maintenance.stop(db, aquarium)
    return _state(db, aquarium)
