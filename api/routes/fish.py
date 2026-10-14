"""
Poissons des aquariums.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from middleware.auth import min_role_required
from models.fish import Fish
from schemas.fish import FishRead, FishCreate, FishUpdate, FishListResponse
from middleware.database import get_db
from models.photo import PhotoType
from services.cleanup import delete_photos
from services import journal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fishes", tags=["fishes"], dependencies=[Depends(min_role_required("consult"))])


@router.post(
    "/",
    response_model=FishRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user"))],
)
def create_fish(fish_in: FishCreate, db: Session = Depends(get_db)):
    try:
        fish = Fish(**fish_in.model_dump())
        db.add(fish)
        journal.livestock_added(db, fish.aquarium_id, fish.name, fish.quantity, fish.date_acquisition)
        db.commit()
        db.refresh(fish)
        return fish
    except Exception:
        logger.exception("Erreur lors de l'ajout d'un poisson")
        raise


@router.patch(
    "/{fish_id}",
    response_model=FishRead,
    dependencies=[Depends(min_role_required("user"))],
)
def update_fish(fish_id: int, update_data: FishUpdate, db: Session = Depends(get_db)):
    try:
        fish = db.query(Fish).filter(Fish.id == fish_id).first()
        if not fish:
            raise HTTPException(status_code=404, detail="Poisson non trouvé")

        updated = False
        for field, value in update_data.model_dump(exclude_unset=True).items():
            if getattr(fish, field) != value:
                setattr(fish, field, value)
                updated = True

        if updated:
            db.commit()
            db.refresh(fish)

        return fish
    except Exception:
        logger.exception("Erreur lors de la mise à jour du poisson")
        raise


@router.delete(
    "/{fish_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("manager"))],
)
def delete_fish(fish_id: int, db: Session = Depends(get_db)):
    try:
        fish = db.query(Fish).filter(Fish.id == fish_id).first()
        if not fish:
            raise HTTPException(status_code=404, detail="Poisson non trouvé")

        delete_photos(db, PhotoType.fishes, fish_id)
        db.delete(fish)
        db.commit()
        return
    except Exception:
        logger.exception("Erreur lors de la suppression du poisson")
        raise


@router.get("/{fish_id}", response_model=FishRead)
def get_fish(fish_id: int, db: Session = Depends(get_db)):
    try:
        fish = db.query(Fish).filter(Fish.id == fish_id).first()
        if not fish:
            raise HTTPException(status_code=404, detail="Poisson non trouvé")
        return fish
    except Exception:
        logger.exception("Erreur lors de la récupération du poisson")
        raise


@router.get("/", response_model=FishListResponse)
def list_fishes(
    aquarium_id: Optional[int] = Query(None, description="Poissons de cet aquarium (tous si absent)"),
    db: Session = Depends(get_db),
):
    try:
        query = db.query(Fish)
        if aquarium_id is not None:
            query = query.filter(Fish.aquarium_id == aquarium_id)
        fishes = query.order_by(Fish.name).all()
        total = len(fishes)
        return {"total": total, "fishes": fishes}
    except Exception:
        logger.exception("Erreur lors du listage des poissons")
        raise