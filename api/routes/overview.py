"""
overview.py (routes)

Vue d'ensemble de la page d'accueil : compteurs globaux, état de chaque
aquarium et liste "à faire", en une seule requête.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from middleware.auth import min_role_required
from middleware.database import get_db
from models.aquarium import Aquarium
from models.controller import Controller
from models.coral import Coral
from models.equipment import Equipment
from models.fault import EquipmentFault
from models.fish import Fish
from models.inventory import InventoryItem
from models.maintenance_task import MaintenanceTask
from models.metric_alert import MetricAlert, MetricAlertSource
from models.invertebrate import Invertebrate
from models.plant import Plant
from models.sensor import Sensor, is_temperature_sensor
from models.water_parameter import WaterParameter
from services.maintenance_task import is_overdue
from services.shared_scope import concerned_ids, scope_label
from schemas.metric_alert import MetricAlertRead

router = APIRouter(prefix="/overview", tags=["overview"], dependencies=[Depends(min_role_required("consult"))])

DUE_SOON_DAYS = 7


def _count_by_aquarium(db: Session, model) -> dict[int, int]:
    # Vivants : somme des quantités (un banc de 5 poissons compte pour 5)
    counted = func.sum(model.quantity) if hasattr(model, "quantity") else func.count(model.id)
    return {aq: int(n or 0) for aq, n in db.query(model.aquarium_id, counted).group_by(model.aquarium_id).all()}


def _is_low_stock(item: InventoryItem) -> bool:
    return item.low_stock_threshold is not None and item.quantity <= item.low_stock_threshold


@router.get("/")
def get_overview(db: Session = Depends(get_db)):
    now = datetime.now()
    due_limit = now + timedelta(days=DUE_SOON_DAYS)

    aquariums = db.query(Aquarium).order_by(Aquarium.name).all()
    aquarium_names = {a.id: a.name for a in aquariums}

    fishes = _count_by_aquarium(db, Fish)
    corals = _count_by_aquarium(db, Coral)
    plants = _count_by_aquarium(db, Plant)
    invertebrates = _count_by_aquarium(db, Invertebrate)
    equipments = _count_by_aquarium(db, Equipment)

    all_ids = [a.id for a in aquariums]
    shared_tasks = {t.id: t for t in db.query(MaintenanceTask).filter(MaintenanceTask.scope != "single")}
    shared_items = {i.id: i for i in db.query(InventoryItem).filter(InventoryItem.scope != "single")}

    # Une alerte de tâche ou de stock partagé compte pour chaque aquarium concerné
    open_alerts: dict[int, int] = {}
    open_metric_alerts = db.query(MetricAlert).filter(MetricAlert.resolved_at.is_(None)).all()
    for alert in open_metric_alerts:
        shared = shared_tasks.get(alert.maintenance_task_id) or shared_items.get(alert.inventory_item_id)
        for aquarium_id in concerned_ids(shared, all_ids) if shared else [alert.aquarium_id]:
            open_alerts[aquarium_id] = open_alerts.get(aquarium_id, 0) + 1
    open_faults = dict(
        db.query(Equipment.aquarium_id, func.count(EquipmentFault.id))
        .join(Equipment, Equipment.id == EquipmentFault.equipment_id)
        .filter(EquipmentFault.resolved_at.is_(None))
        .group_by(Equipment.aquarium_id)
        .all()
    )

    params_by_aquarium: dict[int, list[WaterParameter]] = {}
    for param in db.query(WaterParameter).all():
        params_by_aquarium.setdefault(param.aquarium_id, []).append(param)

    temperature_by_aquarium: dict[int, Sensor] = {}
    for sensor in db.query(Sensor).order_by(Sensor.id).all():
        if is_temperature_sensor(sensor):
            temperature_by_aquarium.setdefault(sensor.aquarium_id, sensor)

    tasks = (
        db.query(MaintenanceTask)
        .filter(MaintenanceTask.next_due_at.isnot(None), MaintenanceTask.next_due_at <= due_limit)
        .order_by(MaintenanceTask.next_due_at)
        .all()
    )
    low_stock_items = [item for item in db.query(InventoryItem).order_by(InventoryItem.name).all() if _is_low_stock(item)]

    # Alertes ouvertes à afficher dans « À faire » : mesures hors cible,
    # capteurs muets, défauts d'équipement (tâches et stock y sont déjà listés)
    alert_items = [
        {
            **MetricAlertRead.model_validate(alert).model_dump(),
            "kind": "metric",
            "aquarium_name": aquarium_names.get(alert.aquarium_id),
        }
        for alert in sorted(open_metric_alerts, key=lambda a: a.created_at, reverse=True)
        if alert.source not in (MetricAlertSource.task_overdue, MetricAlertSource.low_stock)
    ]
    fault_rows = (
        db.query(EquipmentFault, Equipment)
        .outerjoin(Equipment, Equipment.id == EquipmentFault.equipment_id)
        .filter(EquipmentFault.resolved_at.is_(None))
        .order_by(EquipmentFault.created_at.desc())
        .all()
    )
    alert_items += [
        {
            "kind": "fault",
            "id": fault.id,
            "code": fault.code,
            "message": fault.message,
            "equipment_name": equipment.name if equipment else None,
            "aquarium_id": equipment.aquarium_id if equipment else None,
            "aquarium_name": aquarium_names.get(equipment.aquarium_id) if equipment else None,
            "created_at": fault.created_at,
        }
        for fault, equipment in fault_rows
    ]

    aquarium_cards = []
    for aquarium in aquariums:
        params = params_by_aquarium.get(aquarium.id, [])
        reading_dates = [p.last_reading_at for p in params if p.last_reading_at]
        temperature = temperature_by_aquarium.get(aquarium.id)
        aquarium_cards.append({
            "id": aquarium.id,
            "name": aquarium.name,
            "water_type": aquarium.water_type.value,
            "volume": aquarium.volume,
            "open_alerts": open_alerts.get(aquarium.id, 0) + open_faults.get(aquarium.id, 0),
            "out_of_target_parameters": [p.name for p in params if p.in_target is False],
            "overdue_tasks": sum(
                1 for t in tasks if aquarium.id in concerned_ids(t, all_ids) and is_overdue(t.next_due_at)
            ),
            "low_stock_items": sum(1 for i in low_stock_items if aquarium.id in concerned_ids(i, all_ids)),
            "last_reading_at": max(reading_dates) if reading_dates else None,
            "livestock": fishes.get(aquarium.id, 0) + corals.get(aquarium.id, 0)
            + plants.get(aquarium.id, 0) + invertebrates.get(aquarium.id, 0),
            "temperature": {
                "sensor_id": temperature.id,
                "name": temperature.name,
                "value": float(temperature.last_value) if temperature.last_value is not None else None,
            } if temperature else None,
        })

    controllers = db.query(Controller).order_by(Controller.name).all()

    return {
        "counts": {
            "aquariums": len(aquariums),
            "equipments": sum(equipments.values()),
            "fishes": sum(fishes.values()),
            "corals": sum(corals.values()),
            "plants": sum(plants.values()),
            "invertebrates": sum(invertebrates.values()),
            "open_alerts": len(open_metric_alerts) + sum(open_faults.values()),
        },
        "controllers": [
            {"id": c.id, "name": c.name, "technical_name": c.technical_name, "status": c.status} for c in controllers
        ],
        "aquariums": aquarium_cards,
        "todo": {
            "alerts": alert_items,
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "aquarium_id": t.aquarium_id,
                    "aquarium_name": scope_label(t, aquarium_names),
                    "shared": t.scope != "single",
                    "next_due_at": t.next_due_at,
                    "overdue": is_overdue(t.next_due_at),
                }
                for t in tasks
            ],
            "low_stock": [
                {
                    "id": i.id,
                    "name": i.name,
                    "aquarium_id": i.aquarium_id,
                    "aquarium_name": scope_label(i, aquarium_names),
                    "shared": i.scope != "single",
                    "quantity": i.quantity,
                    "unit": i.unit,
                    "low_stock_threshold": i.low_stock_threshold,
                }
                for i in low_stock_items
            ],
        },
    }
