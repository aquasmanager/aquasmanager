"""
Broches des contrôleurs : création, modification, remise à zéro.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from middleware.auth import min_role_required
from models.controller_pin import ControllerPin
from schemas.controller_pins import (
    ControllerPinRead,
    ControllerPinCreate,
    ControllerPinUpdate,
    ControllerPinListResponse,
)
from middleware.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/controller-pins",
    tags=["controller-pins"],
    dependencies=[Depends(min_role_required("consult"))]
)


@router.post(
    "/",
    response_model=ControllerPinRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("manager"))],
)
def create_controller_pin(pin_in: ControllerPinCreate, db: Session = Depends(get_db)):
    try:
        db_pin = ControllerPin(**pin_in.model_dump())
        db.add(db_pin)
        db.commit()
        db.refresh(db_pin)
        return db_pin
    except Exception:
        logger.exception("Erreur lors de l'ajout du pin du contrôleur")
        raise


@router.patch(
    "/{pin_id}",
    response_model=ControllerPinRead,
    dependencies=[Depends(min_role_required("manager"))],
)
def update_controller_pin(pin_id: int, update_data: ControllerPinUpdate, db: Session = Depends(get_db)):
    try:
        controller_pin = db.query(ControllerPin).filter(ControllerPin.id == pin_id).first()
        if not controller_pin:
            raise HTTPException(status_code=404, detail="Pin du contrôleur non trouvé")

        updated = False
        for field, value in update_data.model_dump(exclude_unset=True).items():
            if getattr(controller_pin, field) != value:
                setattr(controller_pin, field, value)
                updated = True

        if updated:
            db.commit()
            db.refresh(controller_pin)

        return controller_pin
    except Exception:
        logger.exception("Erreur lors de la mise à jour du pin du contrôleur")
        raise


@router.patch(
    "/raz/{controller_id}/{pin_id}",
    response_model=ControllerPinRead,
    dependencies=[Depends(min_role_required("manager"))],
)
def raz_controller_pin(controller_id: int, pin_id: int, db: Session = Depends(get_db)):
    try:
        controller_pin = db.query(ControllerPin)\
            .filter(ControllerPin.controller_id == controller_id)\
            .filter(ControllerPin.id == pin_id)\
            .first()

        if not controller_pin:
            raise HTTPException(status_code=404, detail="Pin du contrôleur non trouvé")

        setattr(controller_pin, 'mode', "FREE")
        setattr(controller_pin, 'bus', "FREE")
        controller_pin.label = "FREE"

        db.commit()
        db.refresh(controller_pin)

        return controller_pin
    except Exception:
        logger.exception("Erreur lors de la RAZ du pin du contrôleur")
        raise


@router.delete(
    "/{pin_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("manager"))],
)
def delete_controller_pin(pin_id: int, db: Session = Depends(get_db)):
    try:
        controller_pin = db.query(ControllerPin).filter(ControllerPin.id == pin_id).first()
        if not controller_pin:
            raise HTTPException(status_code=404, detail="Pin du contrôleur non trouvé")

        db.delete(controller_pin)
        db.commit()
        return
    except Exception:
        logger.exception("Erreur lors de la suppression du pin du contrôleur")
        raise


@router.get("/{pin_id}", response_model=ControllerPinRead)
def get_controller_pin(pin_id: int, db: Session = Depends(get_db)):
    try:
        controller_pin = db.query(ControllerPin).filter(ControllerPin.id == pin_id).first()
        if not controller_pin:
            raise HTTPException(status_code=404, detail="Pin du contrôleur non trouvé")
        return controller_pin
    except Exception:
        logger.exception("Erreur lors de la récupération du pin du contrôleur")
        raise


@router.get("/", response_model=ControllerPinListResponse)
def list_controllers_pins(db: Session = Depends(get_db)):
    try:
        controllers_pins = db.query(ControllerPin).all()
        total = len(controllers_pins)
        return {"total": total, "controllers_pins": controllers_pins}
    except Exception:
        logger.exception("Erreur lors du listage des pins des contrôleurs")
        raise


@router.get("/{pin_id}/equipments", response_model=ControllerPinRead)
def get_controller_pin_with_equipments(pin_id: int, db: Session = Depends(get_db)):
    try:
        controller_pin = db.query(ControllerPin).filter(ControllerPin.id == pin_id).first()
        if not controller_pin:
            raise HTTPException(status_code=404, detail="Pin du contrôleur non trouvé")
        return controller_pin
    except Exception:
        logger.exception("Erreur lors de la récupération du pin et de ses équipements")
        raise