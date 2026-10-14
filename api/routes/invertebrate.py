"""
invertebrate.py (routes)

Invertébrés d'un aquarium (anciennement /other_alives).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from middleware.auth import min_role_required
from middleware.database import get_db
from models.invertebrate import Invertebrate
from models.photo import PhotoType
from schemas.invertebrate import (
    InvertebrateCreate,
    InvertebrateListResponse,
    InvertebrateRead,
    InvertebrateUpdate,
)
from services.cleanup import delete_photos
from services import journal

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/invertebrates", tags=["invertebrates"], dependencies=[Depends(min_role_required("consult"))]
)


def _get_or_404(db: Session, invertebrate_id: int) -> Invertebrate:
    invertebrate = db.get(Invertebrate, invertebrate_id)
    if not invertebrate:
        raise HTTPException(status_code=404, detail="Invertébré non trouvé")
    return invertebrate


def query_invertebrates(db: Session, aquarium_id: Optional[int]) -> list[Invertebrate]:
    query = db.query(Invertebrate)
    if aquarium_id is not None:
        query = query.filter(Invertebrate.aquarium_id == aquarium_id)
    return query.order_by(Invertebrate.name).all()


@router.get("/", response_model=InvertebrateListResponse)
def list_invertebrates(
    aquarium_id: Optional[int] = Query(None, description="Invertébrés de cet aquarium (tous si absent)"),
    db: Session = Depends(get_db),
):
    invertebrates = query_invertebrates(db, aquarium_id)
    return {"total": len(invertebrates), "invertebrates": invertebrates}


@router.get("/{invertebrate_id}", response_model=InvertebrateRead)
def get_invertebrate(invertebrate_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, invertebrate_id)


@router.post(
    "/",
    response_model=InvertebrateRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user"))],
)
def create_invertebrate(invertebrate_in: InvertebrateCreate, db: Session = Depends(get_db)):
    invertebrate = Invertebrate(**invertebrate_in.model_dump())
    db.add(invertebrate)
    journal.livestock_added(db, invertebrate.aquarium_id, invertebrate.name, invertebrate.quantity,
                            invertebrate.date_acquisition)
    db.commit()
    db.refresh(invertebrate)
    return invertebrate


@router.patch(
    "/{invertebrate_id}",
    response_model=InvertebrateRead,
    dependencies=[Depends(min_role_required("user"))],
)
def update_invertebrate(invertebrate_id: int, update_data: InvertebrateUpdate, db: Session = Depends(get_db)):
    invertebrate = _get_or_404(db, invertebrate_id)
    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(invertebrate, field, value)
    db.commit()
    db.refresh(invertebrate)
    return invertebrate


@router.delete(
    "/{invertebrate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("manager"))],
)
def delete_invertebrate(invertebrate_id: int, db: Session = Depends(get_db)):
    invertebrate = _get_or_404(db, invertebrate_id)
    delete_photos(db, PhotoType.invertebrates, invertebrate_id)
    db.delete(invertebrate)
    db.commit()
