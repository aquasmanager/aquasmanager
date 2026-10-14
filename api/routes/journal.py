"""
journal.py (routes)

Journal de bord par aquarium : notes datées, affichées aussi sur les courbes
des paramètres d'eau (models/journal.py).
"""

from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from middleware.auth import CARE_ROLES, min_role_required
from middleware.database import get_db
from models.aquarium import Aquarium
from models.journal import JournalEntry

router = APIRouter(prefix="/journal", tags=["Journal"], dependencies=[Depends(min_role_required("consult"))])
# Noter un changement d'eau ou une observation : aussi pour le compte de gardiennage
CARE = [Depends(min_role_required("user", also=CARE_ROLES))]
WRITE = [Depends(min_role_required("user"))]

Category = Literal["note", "livestock", "maintenance", "water_change", "dosing", "problem"]


class JournalEntryIn(BaseModel):
    aquarium_id: int = Field(gt=0)
    occurred_at: Optional[datetime] = None
    category: Category = "note"
    text: str = Field(min_length=1, max_length=500)


class JournalEntryUpdate(BaseModel):
    occurred_at: Optional[datetime] = None
    category: Optional[Category] = None
    text: Optional[str] = Field(default=None, min_length=1, max_length=500)


class JournalEntryRead(BaseModel):
    id: int
    aquarium_id: int
    occurred_at: datetime
    category: str
    text: str
    auto: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _naive(value: Optional[datetime]) -> Optional[datetime]:
    """Dates stockées en UTC sans fuseau (comme le reste de la base)."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


@router.get("/", response_model=List[JournalEntryRead])
def list_entries(
    aquarium_id: int = Query(...),
    since: Optional[datetime] = Query(default=None),
    until: Optional[datetime] = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    query = db.query(JournalEntry).filter(JournalEntry.aquarium_id == aquarium_id)
    if since:
        query = query.filter(JournalEntry.occurred_at >= _naive(since))
    if until:
        query = query.filter(JournalEntry.occurred_at <= _naive(until))
    return query.order_by(JournalEntry.occurred_at.desc(), JournalEntry.id.desc()).limit(limit).all()


@router.post("/", response_model=JournalEntryRead, status_code=status.HTTP_201_CREATED, dependencies=CARE)
def create_entry(payload: JournalEntryIn, db: Session = Depends(get_db)):
    if db.get(Aquarium, payload.aquarium_id) is None:
        raise HTTPException(status_code=404, detail="Aquarium introuvable.")
    entry = JournalEntry(
        aquarium_id=payload.aquarium_id,
        occurred_at=_naive(payload.occurred_at) or datetime.now(),
        category=payload.category,
        text=payload.text.strip(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _get(db: Session, entry_id: int) -> JournalEntry:
    entry = db.get(JournalEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Note introuvable.")
    return entry


@router.patch("/{entry_id}", response_model=JournalEntryRead, dependencies=WRITE)
def update_entry(entry_id: int, payload: JournalEntryUpdate, db: Session = Depends(get_db)):
    entry = _get(db, entry_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("occurred_at") is not None:
        entry.occurred_at = _naive(data["occurred_at"])
    if data.get("category") is not None:
        entry.category = data["category"]
    if data.get("text") is not None:
        entry.text = data["text"].strip()
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=WRITE)
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    db.delete(_get(db, entry_id))
    db.commit()
