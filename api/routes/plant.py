"""
Plantes des aquariums.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from middleware.auth import min_role_required
from models.plant import Plant
from schemas.plant import PlantRead, PlantCreate, PlantUpdate, PlantListResponse
from middleware.database import get_db
from models.photo import PhotoType
from services.cleanup import delete_photos
from services import journal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plants", tags=["Plant"], dependencies=[Depends(min_role_required("consult"))])


@router.post(
    "/",
    response_model=PlantRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user"))],
)
def create_plant(plant_in: PlantCreate, db: Session = Depends(get_db)):
    try:
        plant = Plant(**plant_in.model_dump())
        db.add(plant)
        journal.livestock_added(db, plant.aquarium_id, plant.name, plant.quantity, plant.date_acquisition)
        db.commit()
        db.refresh(plant)
        return plant
    except Exception:
        logger.exception("Erreur lors de l'ajout d'une plante")
        raise


@router.patch(
    "/{plant_id}",
    response_model=PlantRead,
    dependencies=[Depends(min_role_required("user"))],
)
def update_plant(plant_id: int, update_data: PlantUpdate, db: Session = Depends(get_db)):
    try:
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail="Plante non trouvée")

        updated = False
        for field, value in update_data.model_dump(exclude_unset=True).items():
            if getattr(plant, field) != value:
                setattr(plant, field, value)
                updated = True

        if updated:
            db.commit()
            db.refresh(plant)

        return plant
    except Exception:
        logger.exception("Erreur lors de la mise à jour de la plante")
        raise


@router.delete(
    "/{plant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("manager"))],
)
def delete_plant(plant_id: int, db: Session = Depends(get_db)):
    try:
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail="Plante non trouvée")

        delete_photos(db, PhotoType.plants, plant_id)
        db.delete(plant)
        db.commit()
        return
    except Exception:
        logger.exception("Erreur lors de la suppression de la plante")
        raise


@router.get("/{plant_id}", response_model=PlantRead)
def get_plant(plant_id: int, db: Session = Depends(get_db)):
    try:
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail="Plante non trouvée")
        return plant
    except Exception:
        logger.exception("Erreur lors de la récupération de la plante")
        raise


@router.get("/", response_model=PlantListResponse)
def list_plants(
    aquarium_id: Optional[int] = Query(None, description="Plantes de cet aquarium (tous si absent)"),
    db: Session = Depends(get_db),
):
    try:
        query = db.query(Plant)
        if aquarium_id is not None:
            query = query.filter(Plant.aquarium_id == aquarium_id)
        plants = query.order_by(Plant.name).all()
        total = len(plants)
        return {"total": total, "plants": plants}
    except Exception:
        logger.exception("Erreur lors du listage des plantes")
        raise