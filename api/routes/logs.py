"""
Journaux envoyés par les contrôleurs (consultation, filtres).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from middleware.database import get_db
from models.logs import LogModel
from middleware.auth import min_role_required


router = APIRouter(prefix="/logs", tags=["Logs"], dependencies=[Depends(min_role_required("consult"))])


@router.get("/")
def get_logs(
    controller_id: int | None = Query(None, description="Filtrer par contrôleur"),
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Derniers journaux, du plus récent au plus ancien."""
    query = db.query(LogModel)
    if controller_id is not None:
        query = query.filter(LogModel.controller_id == controller_id)
    return query.order_by(LogModel.timestamp.desc()).limit(limit).all()
