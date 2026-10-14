"""
Mesures des capteurs : saisie et correction manuelles.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from middleware.auth import min_role_required
from models.sensor_reading import SensorReading
from schemas.sensor_reading import (
    SensorReadingRead,
    SensorReadingCreate,
    SensorReadingUpdate,
    SensorReadingListResponse,
)
from middleware.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sensors-reading", tags=["sensors-reading"], dependencies=[Depends(min_role_required("consult"))])


@router.post(
    "/",
    response_model=SensorReadingRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user"))],
)
def create_sensor_reading(reading_in: SensorReadingCreate, db: Session = Depends(get_db)):
    try:
        reading = SensorReading(**reading_in.model_dump())
        db.add(reading)
        db.commit()
        db.refresh(reading)
        return reading
    except Exception:
        logger.exception("Erreur lors de l'ajout d'un relevé de capteur")
        raise


@router.patch(
    "/{reading_id}",
    response_model=SensorReadingRead,
    dependencies=[Depends(min_role_required("user"))],
)
def update_sensor_reading(reading_id: int, update_data: SensorReadingUpdate, db: Session = Depends(get_db)):
    try:
        reading = db.query(SensorReading).filter(SensorReading.id == reading_id).first()
        if not reading:
            raise HTTPException(status_code=404, detail="Relevé non trouvé")

        updated = False
        for field, value in update_data.model_dump(exclude_unset=True).items():
            if getattr(reading, field) != value:
                setattr(reading, field, value)
                updated = True

        if updated:
            db.commit()
            db.refresh(reading)

        return reading
    except Exception:
        logger.exception("Erreur lors de la mise à jour du relevé")
        raise


@router.delete(
    "/{reading_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("manager"))],
)
def delete_sensor_reading(reading_id: int, db: Session = Depends(get_db)):
    try:
        reading = db.query(SensorReading).filter(SensorReading.id == reading_id).first()
        if not reading:
            raise HTTPException(status_code=404, detail="Relevé non trouvé")

        db.delete(reading)
        db.commit()
        return
    except Exception:
        logger.exception("Erreur lors de la suppression du relevé")
        raise


@router.get("/{reading_id}", response_model=SensorReadingRead)
def get_sensor_reading(reading_id: int, db: Session = Depends(get_db)):
    try:
        reading = db.query(SensorReading).filter(SensorReading.id == reading_id).first()
        if not reading:
            raise HTTPException(status_code=404, detail="Relevé non trouvé")
        return reading
    except Exception:
        logger.exception("Erreur lors de la récupération du relevé")
        raise


@router.get("/", response_model=SensorReadingListResponse)
def list_sensors_reading(
    sensor_id: Optional[int] = Query(None, description="Filtre par capteur"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Limite le nombre de relevés (les plus récents)"),
    db: Session = Depends(get_db),
):
    try:
        query = db.query(SensorReading)
        if sensor_id is not None:
            query = query.filter(SensorReading.sensor_id == sensor_id)

        if limit is not None:
            # Les `limit` plus récents, mais renvoyés en ordre chronologique
            # (plus simple à consommer tel quel pour une sparkline).
            readings = list(reversed(query.order_by(SensorReading.timestamp.desc()).limit(limit).all()))
        else:
            readings = query.all()

        total = len(readings)
        return {"total": total, "sensors_reading": readings}
    except Exception:
        logger.exception("Erreur lors du listage des relevés")
        raise