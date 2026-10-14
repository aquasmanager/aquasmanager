"""
Aquariums : fiche, caractéristiques, contenu et réglages.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from middleware.auth import min_role_required
from models.aquarium import Aquarium
from models.dashboard_card import DashboardCard, DashboardCardType
from services import cleanup, technical_names
from models.controller import Controller
from models.equipment import Equipment
from models.sensor import Sensor
from schemas.aquarium import AquariumCreate, AquariumRead, AquariumUpdate, AquariumListResponse
from middleware.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/aquariums", tags=["aquariums"], dependencies=[Depends(min_role_required("consult"))])


@router.post(
    "/",
    response_model=AquariumRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user"))],
)
def create_aquarium(aquarium_in: AquariumCreate, db: Session = Depends(get_db)):
    try:
        db_aquarium = Aquarium(**aquarium_in.model_dump())
        db.add(db_aquarium)
        db.flush()
        # Tableau de bord : l'évolution des paramètres d'eau d'office, en tête
        db.add(
            DashboardCard(
                aquarium_id=db_aquarium.id, title="water_trend", type=DashboardCardType.water_trend,
                icon="show_chart", col_span=12, position=0,
            )
        )
        db.commit()
        db.refresh(db_aquarium)
        return db_aquarium
    except Exception:
        logger.exception("Erreur lors de l'ajout de l'aquarium")
        raise


@router.patch(
    "/{aquarium_id}",
    response_model=AquariumRead,
    dependencies=[Depends(min_role_required("user"))],
)
def update_aquarium(aquarium_id: int, update_data: AquariumUpdate, db: Session = Depends(get_db)):
    try:
        aquarium = db.query(Aquarium).filter(Aquarium.id == aquarium_id).first()
        if not aquarium:
            raise HTTPException(status_code=404, detail="Aquarium non trouvé")

        updated = False
        old_name = aquarium.name
        for field, value in update_data.model_dump(exclude_unset=True).items():
            if getattr(aquarium, field) != value:
                setattr(aquarium, field, value)
                updated = True

        if aquarium.name != old_name:
            # Noms techniques « <nom>_<aquarium> » : recalculés, contrôleurs à reflasher
            db.flush()
            for model, kind in ((Equipment, "equipment"), (Sensor, "sensor")):
                for entity in db.query(model).filter(model.aquarium_id == aquarium.id).all():
                    if technical_names.rename(db, entity, kind):
                        db.query(Controller).filter(Controller.id == entity.controller_id).update({Controller.is_dirty: True})
                        db.flush()

        if updated:
            db.commit()
            db.refresh(aquarium)

        return aquarium
    except Exception:
        logger.exception("Erreur lors de la mise à jour de l'aquarium")
        raise


@router.delete(
    "/{aquarium_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("manager"))],
)
def delete_aquarium(aquarium_id: int, db: Session = Depends(get_db)):
    try:
        aquarium = db.query(Aquarium).filter(Aquarium.id == aquarium_id).first()
        if not aquarium:
            raise HTTPException(status_code=404, detail="Aquarium non trouvé")

        cleanup.delete_aquarium(db, aquarium)
        db.commit()
        return
    except HTTPException:
        raise
    except Exception:
        logger.exception("Erreur lors de la suppression de l'aquarium")
        raise


@router.get("/{aquarium_id}", response_model=AquariumRead)
def get_aquarium(aquarium_id: int, db: Session = Depends(get_db)):
    try:
        aquarium = db.query(Aquarium).filter(Aquarium.id == aquarium_id).first()
        if not aquarium:
            raise HTTPException(status_code=404, detail="Aquarium non trouvé")
        return aquarium
    except Exception:
        logger.exception("Erreur lors de la récupération de l'aquarium")
        raise


@router.get("/", response_model=AquariumListResponse)
def list_aquariums(db: Session = Depends(get_db)):
    try:
        aquariums = db.query(Aquarium).all()
        total = len(aquariums)
        return {"total": total, "aquariums": aquariums}
    except Exception:
        logger.exception("Erreur lors du listage des aquariums")
        raise