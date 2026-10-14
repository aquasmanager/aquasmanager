"""
audit.py (routes) — consultation du journal d'activité (administrateurs).
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_
from sqlalchemy.orm import Session

from middleware.auth import min_role_required
from middleware.database import get_db
from models.audit_log import AuditLog

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(min_role_required("admin"))])


class AuditLogRead(BaseModel):
    id: int
    created_at: datetime
    user_id: Optional[int] = None
    username: Optional[str] = None
    method: str
    path: str
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    entity_label: Optional[str] = None
    details: Optional[str] = None
    status_code: int
    client_ip: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AuditLogPage(BaseModel):
    total: int
    items: List[AuditLogRead]


@router.get("/", response_model=AuditLogPage)
def list_audit_logs(
    username: Optional[str] = Query(None, description="Filtre par utilisateur"),
    entity_type: Optional[str] = Query(None, description="Filtre par type d'élément"),
    search: Optional[str] = Query(None, description="Recherche dans l'action ou le nom de l'élément"),
    since: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog)
    if username:
        query = query.filter(AuditLog.username == username)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(AuditLog.action.ilike(pattern), AuditLog.entity_label.ilike(pattern)))
    if since:
        query = query.filter(AuditLog.created_at >= since)
    total = query.count()
    items = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit).all()
    return {"total": total, "items": items}


@router.get("/users", response_model=List[str])
def list_audit_users(db: Session = Depends(get_db)):
    """Utilisateurs présents dans le journal (pour le filtre)."""
    rows = db.query(AuditLog.username).filter(AuditLog.username.isnot(None)).distinct().all()
    return sorted(row[0] for row in rows)
