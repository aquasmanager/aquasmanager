"""
equipment_usage.py (routes)

Usure (heures, entretien) et consommation électrique des équipements.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from middleware.auth import min_role_required
from middleware.database import get_db
from models.equipment import Equipment
from services.equipment_usage import get_energy_settings, get_usage, mark_serviced, usage_report

router = APIRouter(prefix="/equipment-usage", tags=["equipment usage"], dependencies=[Depends(min_role_required("consult"))])


class UsageUpdate(BaseModel):
    power_watts: Optional[float] = Field(default=None, ge=0, le=10000)
    service_interval_hours: Optional[int] = Field(default=None, ge=1, le=200000)
    service_label: Optional[str] = Field(default=None, max_length=80)


class EnergySettingsIO(BaseModel):
    price_per_kwh: float = Field(ge=0, le=5)


def _equipment_or_404(db: Session, equipment_id: int) -> Equipment:
    equipment = db.get(Equipment, equipment_id)
    if equipment is None:
        raise HTTPException(status_code=404, detail="Équipement non trouvé")
    return equipment


@router.get("/settings", response_model=EnergySettingsIO)
def read_settings(db: Session = Depends(get_db)):
    return get_energy_settings(db)


@router.put("/settings", response_model=EnergySettingsIO, dependencies=[Depends(min_role_required("manager"))])
def update_settings(payload: EnergySettingsIO, db: Session = Depends(get_db)):
    conf = get_energy_settings(db)
    conf.price_per_kwh = payload.price_per_kwh
    db.commit()
    return conf


@router.get("/")
def list_usage(aquarium_id: Optional[int] = Query(None), db: Session = Depends(get_db)) -> List[dict]:
    price = get_energy_settings(db).price_per_kwh
    query = db.query(Equipment)
    if aquarium_id is not None:
        query = query.filter(Equipment.aquarium_id == aquarium_id)
    rows = [usage_report(db, e, price) for e in query.order_by(Equipment.name).all()]
    db.commit()  # lignes d'usure créées au premier affichage
    return rows


@router.put("/{equipment_id}", dependencies=[Depends(min_role_required("user"))])
def update_usage(equipment_id: int, payload: UsageUpdate, db: Session = Depends(get_db)) -> dict:
    equipment = _equipment_or_404(db, equipment_id)
    usage, _ = get_usage(db, equipment_id)
    usage.power_watts = payload.power_watts
    if usage.service_interval_hours != payload.service_interval_hours:
        usage.service_task_created = False
    usage.service_interval_hours = payload.service_interval_hours
    usage.service_label = (payload.service_label or "").strip() or None
    db.commit()
    return usage_report(db, equipment, get_energy_settings(db).price_per_kwh)


@router.post("/{equipment_id}/serviced", dependencies=[Depends(min_role_required("user"))])
def serviced(equipment_id: int, db: Session = Depends(get_db)) -> dict:
    """Entretien fait (ampoule changée...) : le compteur d'entretien repart de zéro."""
    equipment = _equipment_or_404(db, equipment_id)
    mark_serviced(db, equipment_id)
    db.commit()
    return usage_report(db, equipment, get_energy_settings(db).price_per_kwh)
