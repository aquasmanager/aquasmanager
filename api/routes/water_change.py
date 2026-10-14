"""
water_change.py (routes)

Changements d'eau : enregistrement (volume, sel décompté du stock, tâche
validée), liste et suppression (sel recrédité, note du journal retirée).
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from middleware.auth import CARE_ROLES, min_role_required
from middleware.database import get_db
from models.aquarium import Aquarium
from models.inventory import InventoryItem, InventoryMovement
from models.journal import JournalEntry
from models.maintenance_task import MaintenanceTask, MaintenanceTaskCompletion
from models.water_change import WaterChange
from services import journal
from services.maintenance_task import compute_next_due

router = APIRouter(prefix="/water-changes", tags=["Water changes"], dependencies=[Depends(min_role_required("consult"))])
CARE = [Depends(min_role_required("user", also=CARE_ROLES))]


class WaterChangeIn(BaseModel):
    aquarium_id: int = Field(gt=0)
    performed_at: Optional[datetime] = None
    volume_l: float = Field(gt=0, le=100000)
    salt_item_id: Optional[int] = Field(default=None, gt=0)
    salt_amount: Optional[float] = Field(default=None, gt=0, le=100000)
    note: Optional[str] = Field(default=None, max_length=300)
    # Tâche d'entretien « changement d'eau » validée en même temps
    complete_task_id: Optional[int] = Field(default=None, gt=0)


class WaterChangeRead(BaseModel):
    id: int
    aquarium_id: int
    performed_at: datetime
    volume_l: float
    salt_item_id: Optional[int] = None
    salt_item_name: Optional[str] = None
    salt_unit: Optional[str] = None
    salt_amount: Optional[float] = None
    note: Optional[str] = None
    percent: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


def _naive(value: Optional[datetime]) -> Optional[datetime]:
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _fmt(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def _read(db: Session, change: WaterChange, volume: Optional[int] = None) -> dict:
    item = db.get(InventoryItem, change.salt_item_id) if change.salt_item_id else None
    if volume is None:
        aquarium = db.get(Aquarium, change.aquarium_id)
        volume = aquarium.volume if aquarium else None
    return {
        "id": change.id,
        "aquarium_id": change.aquarium_id,
        "performed_at": change.performed_at,
        "volume_l": change.volume_l,
        "salt_item_id": change.salt_item_id,
        "salt_item_name": item.name if item else None,
        "salt_unit": item.unit if item else None,
        "salt_amount": change.salt_amount,
        "note": change.note,
        "percent": round(change.volume_l / volume * 100, 1) if volume else None,
    }


@router.get("/", response_model=List[WaterChangeRead])
def list_changes(aquarium_id: int = Query(...), limit: int = Query(default=200, ge=1, le=1000),
                 db: Session = Depends(get_db)):
    aquarium = db.get(Aquarium, aquarium_id)
    changes = (
        db.query(WaterChange)
        .filter(WaterChange.aquarium_id == aquarium_id)
        .order_by(WaterChange.performed_at.desc())
        .limit(limit)
        .all()
    )
    return [_read(db, c, aquarium.volume if aquarium else None) for c in changes]


@router.post("/", response_model=WaterChangeRead, status_code=status.HTTP_201_CREATED, dependencies=CARE)
def create_change(payload: WaterChangeIn, db: Session = Depends(get_db)):
    aquarium = db.get(Aquarium, payload.aquarium_id)
    if aquarium is None:
        raise HTTPException(status_code=404, detail="Aquarium introuvable.")
    performed_at = _naive(payload.performed_at) or datetime.now()
    item = None
    if payload.salt_item_id:
        item = db.get(InventoryItem, payload.salt_item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Article du stock introuvable.")
        if not payload.salt_amount:
            raise HTTPException(status_code=422, detail="Indique la quantité de sel utilisée.")
    change = WaterChange(
        aquarium_id=aquarium.id,
        performed_at=performed_at,
        volume_l=payload.volume_l,
        salt_item_id=item.id if item else None,
        salt_amount=payload.salt_amount if item else None,
        note=(payload.note or "").strip() or None,
    )
    db.add(change)
    date_label = performed_at.strftime("%d/%m/%Y")
    if item:
        db.add(InventoryMovement(item_id=item.id, delta=-payload.salt_amount,
                                 note=f"Changement d'eau du {date_label} ({aquarium.name})"))
        item.quantity = round(item.quantity - payload.salt_amount, 6)
    if payload.complete_task_id:
        task = db.get(MaintenanceTask, payload.complete_task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Tâche introuvable.")
        db.add(MaintenanceTaskCompletion(task_id=task.id, completed_at=performed_at, note="Changement d'eau enregistré"))
        task.last_completed_at = performed_at
        task.next_due_at = compute_next_due(task.recurrence, task.recurrence_days, performed_at)
    percent = f" ({_fmt(payload.volume_l / aquarium.volume * 100)} %)" if aquarium.volume else ""
    salt = f" · {_fmt(payload.salt_amount)} {item.unit} de {item.name}" if item else ""
    note = f" · {change.note}" if change.note else ""
    entry = journal.add(db, aquarium.id, "water_change",
                        f"Changement d'eau {_fmt(payload.volume_l)} L{percent}{salt}{note}", performed_at)
    change.journal_entry_id = entry.id if entry else None
    db.commit()
    db.refresh(change)
    return _read(db, change, aquarium.volume)


@router.delete("/{change_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(min_role_required("user"))])
def delete_change(change_id: int, db: Session = Depends(get_db)):
    """Supprime l'enregistrement : sel recrédité au stock, note du journal retirée."""
    change = db.get(WaterChange, change_id)
    if change is None:
        raise HTTPException(status_code=404, detail="Changement d'eau introuvable.")
    if change.salt_item_id and change.salt_amount:
        item = db.get(InventoryItem, change.salt_item_id)
        if item:
            db.add(InventoryMovement(item_id=item.id, delta=change.salt_amount,
                                     note="Changement d'eau supprimé : sel recrédité"))
            item.quantity = round(item.quantity + change.salt_amount, 6)
    if change.journal_entry_id:
        entry = db.get(JournalEntry, change.journal_entry_id)
        if entry:
            db.delete(entry)
    db.delete(change)
    db.commit()
