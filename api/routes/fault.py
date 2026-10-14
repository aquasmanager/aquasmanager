"""
Défauts des équipements : liste et acquittement.
"""

import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from middleware.auth import min_role_required
from middleware.database import get_db
from models.fault import EquipmentFault
from schemas.fault import EquipmentFaultRead, EquipmentFaultListResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/faults", tags=["faults"], dependencies=[Depends(min_role_required("consult"))])


@router.get("/", response_model=EquipmentFaultListResponse)
def list_faults(resolved: bool | None = None, db: Session = Depends(get_db)):
    query = db.query(EquipmentFault)
    if resolved is True:
        query = query.filter(EquipmentFault.resolved_at.isnot(None))
    elif resolved is False:
        query = query.filter(EquipmentFault.resolved_at.is_(None))

    faults = query.order_by(EquipmentFault.created_at.desc()).all()
    return {"total": len(faults), "faults": faults}


@router.post(
    "/{fault_id}/acknowledge",
    response_model=EquipmentFaultRead,
    dependencies=[Depends(min_role_required("user"))],
)
def acknowledge_fault(fault_id: int, db: Session = Depends(get_db)):
    """
    Marque une alerte non-latchée (interlock capteur, notification) comme
    lue. Ne s'applique pas aux défauts latchés (LEVEL_TIMEOUT,
    TOO_MANY_CYCLES) : ceux-ci doivent être acquittés via
    /equipments/{id}/fault/clear pour être réellement relevés sur l'ESP.
    """
    fault = db.query(EquipmentFault).filter(EquipmentFault.id == fault_id).first()
    if not fault:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerte non trouvée")
    if fault.latched:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce défaut nécessite une réinitialisation via /equipments/{id}/fault/clear",
        )
    if fault.resolved_at is None:
        fault.resolved_at = datetime.now()
        db.commit()
        db.refresh(fault)
    return fault
