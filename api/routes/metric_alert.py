"""
Alertes sur les paramètres d'eau hors cible : liste et acquittement.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from middleware.auth import min_role_required
from middleware.database import get_db
from sqlalchemy import or_, select
from models.inventory import InventoryItem
from models.maintenance_task import MaintenanceTask
from services.shared_scope import concerns_aquarium
from models.metric_alert import MetricAlert
from schemas.metric_alert import MetricAlertRead
from services.metric_alerts import current_value_for_alert

router = APIRouter(prefix="/metric-alerts", tags=["Metric Alerts"], dependencies=[Depends(min_role_required("consult"))])


@router.get("/", response_model=List[MetricAlertRead])
def list_metric_alerts(
    aquarium_id: int = Query(...),
    resolved: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    # Alertes de l'aquarium, plus celles des tâches et articles partagés qui le concernent
    shared_tasks = select(MaintenanceTask.id).where(concerns_aquarium(MaintenanceTask, aquarium_id))
    shared_items = select(InventoryItem.id).where(concerns_aquarium(InventoryItem, aquarium_id))
    query = db.query(MetricAlert).filter(
        or_(
            MetricAlert.aquarium_id == aquarium_id,
            MetricAlert.maintenance_task_id.in_(shared_tasks),
            MetricAlert.inventory_item_id.in_(shared_items),
        )
    )
    if resolved is True:
        query = query.filter(MetricAlert.resolved_at.isnot(None))
    elif resolved is False:
        query = query.filter(MetricAlert.resolved_at.is_(None))

    return query.order_by(MetricAlert.created_at.desc()).all()


@router.post(
    "/{alert_id}/acknowledge",
    response_model=MetricAlertRead,
    dependencies=[Depends(min_role_required("user"))],
)
def acknowledge_metric_alert(alert_id: int, db: Session = Depends(get_db)):
    """
    Acquitte (masque) une alerte même si la valeur est toujours hors
    cible. Elle ne réapparaît pas au prochain cycle d'évaluation tant que
    rien n'a changé : seulement si une nouvelle valeur, elle aussi hors
    cible, est constatée ensuite (voir services/metric_alerts._sync_alert).
    """
    alert = db.query(MetricAlert).filter(MetricAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerte non trouvée")
    if alert.resolved_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cette alerte est déjà résolue")

    alert.resolved_at = datetime.now()
    alert.resolved_value = current_value_for_alert(db, alert)
    alert.acknowledged = True

    db.commit()
    db.refresh(alert)
    return alert
