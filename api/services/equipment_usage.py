"""
Usure et consommation électrique des équipements (voir models/equipment_usage.py).
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.equipment import Equipment
from models.equipment_activation import EquipmentActivation
from models.equipment_usage import EnergySettings, EquipmentUsage
from models.maintenance_task import MaintenanceTask

logger = logging.getLogger(__name__)

WINDOW_DAYS = 30


def get_usage(db: Session, equipment_id: int) -> tuple[EquipmentUsage, bool]:
    """Ligne d'usure de l'équipement ; créée au besoin avec les activations déjà connues (created=True)."""
    usage = db.get(EquipmentUsage, equipment_id)
    if usage is not None:
        return usage, False
    closed = (
        db.query(func.coalesce(func.sum(EquipmentActivation.duration_seconds), 0))
        .filter(EquipmentActivation.equipment_id == equipment_id, EquipmentActivation.duration_seconds.isnot(None))
        .scalar()
    )
    usage = EquipmentUsage(equipment_id=equipment_id, runtime_seconds=int(closed or 0), runtime_at_service=0)
    db.add(usage)
    db.flush()
    return usage, True


def record_runtime(db: Session, equipment_id: int, seconds: int) -> None:
    """Activation terminée : ajoute sa durée au compteur (appelé par le driver MQTT)."""
    usage, created = get_usage(db, equipment_id)
    if not created:  # une ligne créée à l'instant compte déjà cette activation
        usage.runtime_seconds += max(0, seconds)


def get_energy_settings(db: Session) -> EnergySettings:
    conf = db.get(EnergySettings, 1)
    if conf is None:
        conf = EnergySettings(id=1)
        db.add(conf)
        db.commit()
        db.refresh(conf)
    return conf


def _open_activation(db: Session, equipment_id: int) -> Optional[EquipmentActivation]:
    return (
        db.query(EquipmentActivation)
        .filter(EquipmentActivation.equipment_id == equipment_id, EquipmentActivation.ended_at.is_(None))
        .order_by(EquipmentActivation.started_at.desc())
        .first()
    )


def _seconds_in_window(db: Session, equipment_id: int, start: datetime, end: datetime) -> int:
    total = 0.0
    for activation in (
        db.query(EquipmentActivation)
        .filter(
            EquipmentActivation.equipment_id == equipment_id,
            EquipmentActivation.started_at < end,
            (EquipmentActivation.ended_at.is_(None)) | (EquipmentActivation.ended_at > start),
        )
        .all()
    ):
        begin = max(activation.started_at, start)
        finish = min(activation.ended_at or end, end)
        total += max(0.0, (finish - begin).total_seconds())
    return int(total)


def usage_report(db: Session, equipment: Equipment, price_per_kwh: float, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now()
    usage, _ = get_usage(db, equipment.id)
    running = _open_activation(db, equipment.id)
    ongoing = (now - running.started_at).total_seconds() if running else 0
    total_seconds = usage.runtime_seconds + ongoing
    since_service = max(0.0, total_seconds - usage.runtime_at_service)
    window_seconds = _seconds_in_window(db, equipment.id, now - timedelta(days=WINDOW_DAYS), now)
    kwh = (usage.power_watts or 0) * window_seconds / 3600 / 1000 if usage.power_watts else None
    interval = usage.service_interval_hours
    return {
        "equipment_id": equipment.id,
        "name": equipment.name,
        "category": equipment.category.value if hasattr(equipment.category, "value") else str(equipment.category),
        "aquarium_id": equipment.aquarium_id,
        "running": running is not None,
        "power_watts": usage.power_watts,
        "hours_total": round(total_seconds / 3600, 1),
        "hours_30d": round(window_seconds / 3600, 1),
        "kwh_30d": round(kwh, 2) if kwh is not None else None,
        "cost_30d": round(kwh * price_per_kwh, 2) if kwh is not None else None,
        "service_label": usage.service_label,
        "service_interval_hours": interval,
        "hours_since_service": round(since_service / 3600, 1),
        "service_progress": round(since_service / 3600 / interval, 3) if interval else None,
        "serviced_at": usage.serviced_at,
    }


def check_service_due(db: Session, now: Optional[datetime] = None) -> int:
    """Entretien atteint : crée une tâche (une seule par cycle). Renvoie le nombre de tâches créées."""
    now = now or datetime.now()
    created = 0
    for usage in db.query(EquipmentUsage).filter(
        EquipmentUsage.service_interval_hours.isnot(None), EquipmentUsage.service_task_created.is_(False)
    ):
        equipment = db.get(Equipment, usage.equipment_id)
        if equipment is None:
            continue
        running = _open_activation(db, equipment.id)
        total = usage.runtime_seconds + ((now - running.started_at).total_seconds() if running else 0)
        if (total - usage.runtime_at_service) / 3600 < usage.service_interval_hours:
            continue
        label = usage.service_label or "Entretien"
        db.add(
            MaintenanceTask(
                aquarium_id=equipment.aquarium_id,
                title=f"{label} : {equipment.name}"[:100],
                description=f"{usage.service_interval_hours} h de fonctionnement atteintes depuis le dernier entretien.",
                next_due_at=now,
            )
        )
        usage.service_task_created = True
        created += 1
    if created:
        db.commit()
        logger.info("%d tâche(s) d'entretien d'équipement créée(s)", created)
    return created


def mark_serviced(db: Session, equipment_id: int, now: Optional[datetime] = None) -> EquipmentUsage:
    now = now or datetime.now()
    usage, _ = get_usage(db, equipment_id)
    running = _open_activation(db, equipment_id)
    usage.runtime_at_service = usage.runtime_seconds + int((now - running.started_at).total_seconds() if running else 0)
    usage.serviced_at = now
    usage.service_task_created = False
    return usage
