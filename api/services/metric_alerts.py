"""
services/metric_alerts.py

Ouvre/ferme des MetricAlert en comparant les valeurs courantes des
paramètres d'eau manuels et des capteurs configurés avec une cible (via une
DashboardCard température/paramètre d'eau) à leur target_min/target_max.
Appelé périodiquement (voir main.py) plutôt que branché directement dans
les routes de saisie ou le driver MQTT, pour ne pas toucher à du code déjà
sensible en prod.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.water_parameter import WaterParameter
from services.maintenance_task import days_overdue as task_days_overdue, is_overdue as is_task_overdue
from services.shared_scope import scope_label
from models.dashboard_card import DashboardCard, DashboardCardType
from models.sensor import Sensor, is_temperature_sensor
from models.sensor_reading import SensorReading
from models.maintenance_task import MaintenanceTask
from models.inventory import InventoryItem
from models.aquarium import Aquarium
from models.metric_alert import MetricAlert, MetricAlertSource

logger = logging.getLogger(__name__)


def purge_old_metric_alerts(db: Session, retention_days: int) -> int:
    """
    Supprime les alertes métriques résolues depuis plus de retention_days.
    Les alertes encore ouvertes (resolved_at NULL) ne sont jamais purgées,
    quel que soit leur âge.
    """
    cutoff = datetime.now() - timedelta(days=retention_days)
    deleted = (
        db.query(MetricAlert)
        .filter(MetricAlert.resolved_at.isnot(None), MetricAlert.resolved_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    if deleted:
        logger.info("Purge des alertes métriques : %d ligne(s) de plus de %dj supprimée(s).", deleted, retention_days)
    return deleted


def _is_out_of_target(value: Optional[float], target_min: Optional[float], target_max: Optional[float]) -> bool:
    if value is None:
        return False
    if target_min is None and target_max is None:
        return False
    lo = target_min if target_min is not None else float("-inf")
    hi = target_max if target_max is not None else float("inf")
    return value < lo or value > hi


def _values_match(a: Optional[float], b: Optional[float]) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) < 1e-9


@dataclass
class AlertEvent:
    kind: Literal["opened", "resolved"]
    alert: MetricAlert
    value: Optional[float]
    previous: Optional[MetricAlert]


def _collect(events: list[AlertEvent], event: Optional[AlertEvent]) -> None:
    if event is not None:
        events.append(event)


def _sync_alert(
    db: Session,
    *,
    is_out: bool,
    aquarium_id: int,
    source: MetricAlertSource,
    water_parameter_id: Optional[int] = None,
    dashboard_card_id: Optional[int] = None,
    maintenance_task_id: Optional[int] = None,
    inventory_item_id: Optional[int] = None,
    sensor_id: Optional[int] = None,
    label: str,
    unit: Optional[str] = None,
    value: Optional[float],
    target_min: Optional[float] = None,
    target_max: Optional[float] = None,
    open_alert: Optional[MetricAlert],
    last_alert: Optional[MetricAlert] = None,
    ack_value: Optional[float] = None,
) -> Optional[AlertEvent]:
    if is_out and not open_alert:
        # Une alerte acquittée manuellement (encore hors cible au moment de
        # l'acquittement) ne doit pas se rouvrir toute seule au prochain
        # cycle si rien n'a changé depuis : seulement quand une nouvelle
        # valeur, elle aussi hors cible, est constatée.
        compared = ack_value if ack_value is not None else value
        if last_alert and last_alert.acknowledged and _values_match(last_alert.resolved_value, compared):
            return None
        alert = MetricAlert(
            aquarium_id=aquarium_id,
            source=source,
            water_parameter_id=water_parameter_id,
            dashboard_card_id=dashboard_card_id,
            maintenance_task_id=maintenance_task_id,
            inventory_item_id=inventory_item_id,
            sensor_id=sensor_id,
            label=label,
            unit=unit,
            initial_value=value if value is not None else 0,
            target_min=target_min,
            target_max=target_max,
        )
        db.add(alert)
        logger.info("Alerte ouverte : %s (valeur=%s, cible=%s-%s)", label, value, target_min, target_max)
        return AlertEvent("opened", alert, value, last_alert)
    elif not is_out and open_alert:
        open_alert.resolved_at = datetime.now()
        open_alert.resolved_value = value
        logger.info("Alerte résolue : %s (valeur=%s)", label, value)
        return AlertEvent("resolved", open_alert, value, last_alert)
    return None


def _open_alerts_by(db: Session, source: MetricAlertSource, id_column: str) -> dict:
    return {
        getattr(a, id_column): a
        for a in db.query(MetricAlert).filter(MetricAlert.source == source, MetricAlert.resolved_at.is_(None)).all()
    }


def _last_alerts_by(db: Session, source: MetricAlertSource, id_column: str) -> dict:
    """La plus récente alerte (peu importe son statut) par entité, pour
    détecter un acquittement récent lors de la prochaine évaluation."""
    result: dict = {}
    rows = db.query(MetricAlert).filter(MetricAlert.source == source).order_by(MetricAlert.created_at.desc()).all()
    for a in rows:
        key = getattr(a, id_column)
        if key not in result:
            result[key] = a
    return result


def evaluate_metric_alerts(db: Session) -> None:
    events: list[AlertEvent] = []
    open_by_water_param = _open_alerts_by(db, MetricAlertSource.water_parameter, "water_parameter_id")
    open_by_card = _open_alerts_by(db, MetricAlertSource.sensor, "dashboard_card_id")
    open_by_task = _open_alerts_by(db, MetricAlertSource.task_overdue, "maintenance_task_id")
    open_by_item = _open_alerts_by(db, MetricAlertSource.low_stock, "inventory_item_id")

    last_by_water_param = _last_alerts_by(db, MetricAlertSource.water_parameter, "water_parameter_id")
    last_by_card = _last_alerts_by(db, MetricAlertSource.sensor, "dashboard_card_id")
    last_by_task = _last_alerts_by(db, MetricAlertSource.task_overdue, "maintenance_task_id")
    last_by_item = _last_alerts_by(db, MetricAlertSource.low_stock, "inventory_item_id")

    for param in db.query(WaterParameter).all():
        _collect(events, _sync_alert(
            db,
            is_out=_is_out_of_target(param.last_value, param.target_min, param.target_max),
            aquarium_id=param.aquarium_id,
            source=MetricAlertSource.water_parameter,
            water_parameter_id=param.id,
            label=param.name,
            unit=param.unit,
            value=param.last_value,
            target_min=param.target_min,
            target_max=param.target_max,
            open_alert=open_by_water_param.get(param.id),
            last_alert=last_by_water_param.get(param.id),
        ))

    sensor_cards = (
        db.query(DashboardCard)
        .filter(
            DashboardCard.type.in_([DashboardCardType.temperature, DashboardCardType.water_param]),
            DashboardCard.sensor_id.isnot(None),
        )
        .all()
    )
    # Maintenance en cours (changement d'eau) : alertes de capteurs suspendues
    from services.maintenance import paused_aquarium_ids

    paused = paused_aquarium_ids(db)
    for card in sensor_cards:
        if card.aquarium_id in paused:
            continue
        sensor = db.query(Sensor).filter(Sensor.id == card.sensor_id).first()
        value = sensor.last_value if sensor else None
        _collect(events, _sync_alert(
            db,
            is_out=_is_out_of_target(value, card.target_min, card.target_max),
            aquarium_id=card.aquarium_id,
            source=MetricAlertSource.sensor,
            dashboard_card_id=card.id,
            label=card.title,
            unit=card.unit,
            value=value,
            target_min=card.target_min,
            target_max=card.target_max,
            open_alert=open_by_card.get(card.id),
            last_alert=last_by_card.get(card.id),
        ))

    for task in db.query(MaintenanceTask).all():
        task_overdue = is_task_overdue(task.next_due_at)
        overdue_days = task_days_overdue(task.next_due_at) if task_overdue else 0
        _collect(events, _sync_alert(
            db,
            is_out=task_overdue,
            aquarium_id=task.aquarium_id,
            source=MetricAlertSource.task_overdue,
            maintenance_task_id=task.id,
            label=task.title,
            unit="j de retard",
            value=overdue_days,
            open_alert=open_by_task.get(task.id),
            last_alert=last_by_task.get(task.id),
        ))

    for item in db.query(InventoryItem).all():
        is_low = item.low_stock_threshold is not None and item.quantity <= item.low_stock_threshold
        _collect(events, _sync_alert(
            db,
            is_out=is_low,
            aquarium_id=item.aquarium_id,
            source=MetricAlertSource.low_stock,
            inventory_item_id=item.id,
            label=item.name,
            unit=item.unit,
            value=item.quantity,
            target_min=item.low_stock_threshold,
            open_alert=open_by_item.get(item.id),
            last_alert=last_by_item.get(item.id),
        ))

    _evaluate_stale_sensors(db, events)

    db.commit()
    notify_alert_events(db, events)


STALE_MIN_DELAY = timedelta(minutes=15)
STALE_INTERVAL_FACTOR = 5


def _last_reading_times(db: Session) -> dict[int, datetime]:
    return dict(db.query(SensorReading.sensor_id, func.max(SensorReading.timestamp)).group_by(SensorReading.sensor_id).all())


def _evaluate_stale_sensors(db: Session, events: list) -> None:
    """
    Sonde muette : une sonde de température (mesure périodique) qui n'a rien
    envoyé depuis 15 min ou 5 intervalles. Les capteurs de niveau ne publient
    qu'au changement d'état : un long silence est normal, ils sont exclus.
    Seules les sondes ayant déjà envoyé au moins une mesure sont surveillées.
    """
    open_by_sensor = _open_alerts_by(db, MetricAlertSource.sensor_stale, "sensor_id")
    last_by_sensor = _last_alerts_by(db, MetricAlertSource.sensor_stale, "sensor_id")
    last_times = _last_reading_times(db)
    now = datetime.now()
    from services.maintenance import paused_aquarium_ids

    paused = paused_aquarium_ids(db)
    for sensor in db.query(Sensor).all():
        last_time = last_times.get(sensor.id)
        if not is_temperature_sensor(sensor) or last_time is None or sensor.aquarium_id in paused:
            continue
        delay = max(STALE_MIN_DELAY, timedelta(seconds=STALE_INTERVAL_FACTOR * (sensor.interval or 30)))
        silence = now - last_time
        _collect(events, _sync_alert(
            db,
            is_out=silence > delay,
            aquarium_id=sensor.aquarium_id,
            source=MetricAlertSource.sensor_stale,
            sensor_id=sensor.id,
            label=sensor.name,
            unit="min",
            value=float(int(silence.total_seconds() // 60)),
            open_alert=open_by_sensor.get(sensor.id),
            last_alert=last_by_sensor.get(sensor.id),
            # Acquittement valable jusqu'à la prochaine mesure reçue
            ack_value=last_time.timestamp(),
        ))


def current_value_for_alert(db: Session, alert: MetricAlert) -> Optional[float]:
    """Revalue la source d'une alerte au moment de l'acquittement (pas la
    valeur d'ouverture, potentiellement ancienne) : sert à savoir, à la
    prochaine évaluation, si une mesure différente est apparue depuis."""
    if alert.source == MetricAlertSource.water_parameter and alert.water_parameter_id:
        param = db.query(WaterParameter).filter(WaterParameter.id == alert.water_parameter_id).first()
        return param.last_value if param else None

    if alert.source == MetricAlertSource.sensor and alert.dashboard_card_id:
        card = db.query(DashboardCard).filter(DashboardCard.id == alert.dashboard_card_id).first()
        if not card or not card.sensor_id:
            return None
        sensor = db.query(Sensor).filter(Sensor.id == card.sensor_id).first()
        return sensor.last_value if sensor else None

    if alert.source == MetricAlertSource.task_overdue and alert.maintenance_task_id:
        task = db.query(MaintenanceTask).filter(MaintenanceTask.id == alert.maintenance_task_id).first()
        if not task or not task.next_due_at:
            return None
        return float(task_days_overdue(task.next_due_at))

    if alert.source == MetricAlertSource.sensor_stale and alert.sensor_id:
        last_time = _last_reading_times(db).get(alert.sensor_id)
        return last_time.timestamp() if last_time else None

    if alert.source == MetricAlertSource.low_stock and alert.inventory_item_id:
        item = db.query(InventoryItem).filter(InventoryItem.id == alert.inventory_item_id).first()
        return item.quantity if item else None

    return None


# --- Notifications ---

# Ne pas renotifier une alerte qui se rouvre peu après s'être fermée (valeur
# qui oscille autour d'une limite).
RENOTIFY_COOLDOWN = timedelta(minutes=30)


def _fmt(value: Optional[float]) -> str:
    if value is None:
        return "--"
    return f"{value:g}"


def _describe(alert: MetricAlert, value: Optional[float]) -> str:
    unit = f" {alert.unit}" if alert.unit else ""
    if alert.source == MetricAlertSource.task_overdue:
        return f"Tâche en retard : {alert.label} ({_fmt(value)} j)"
    if alert.source == MetricAlertSource.sensor_stale:
        if alert.resolved_at is not None:
            return f"{alert.label} : mesures de nouveau reçues"
        return f"{alert.label} : aucune mesure depuis {_fmt(value)} min (sonde débranchée, en panne ou contrôleur hors ligne ?)"
    if alert.source == MetricAlertSource.low_stock:
        return f"Stock bas : {alert.label} {_fmt(value)}{unit} (seuil {_fmt(alert.target_min)}{unit})"
    target = f"{_fmt(alert.target_min)}–{_fmt(alert.target_max)}{unit}"
    return f"{alert.label} : {_fmt(value)}{unit} (cible {target})"


def _in_cooldown(event: AlertEvent) -> bool:
    previous = event.previous
    return (
        previous is not None
        and previous.resolved_at is not None
        and datetime.now() - previous.resolved_at < RENOTIFY_COOLDOWN
    )


def notify_alert_events(db: Session, events: list[AlertEvent]) -> None:
    """
    Capteurs (température...) : un message par alerte, priorité haute, et un
    message au retour dans la cible. Paramètres d'eau, tâches et stock : un
    seul message regroupé par évaluation.
    """
    from services.notify import dispatch_alert

    if not events:
        return
    names = {a.id: a.name for a in db.query(Aquarium).all()}
    grouped: list[str] = []

    for event in events:
        alert = event.alert
        aquarium = names.get(alert.aquarium_id, "?")
        # Tâche ou article partagé : « Tous les aquariums » ou la liste des bacs
        shared = None
        if alert.maintenance_task_id:
            shared = db.get(MaintenanceTask, alert.maintenance_task_id)
        elif alert.inventory_item_id:
            shared = db.get(InventoryItem, alert.inventory_item_id)
        if shared is not None and shared.scope != "single":
            aquarium = scope_label(shared, names)
        if alert.source in (MetricAlertSource.sensor, MetricAlertSource.sensor_stale):
            stale = alert.source == MetricAlertSource.sensor_stale
            if event.kind == "opened" and not _in_cooldown(event):
                dispatch_alert(
                    f"[AquasManager] {aquarium} — {alert.label} " + ("muette" if stale else "hors cible"),
                    _describe(alert, event.value),
                    priority="high",
                )
                alert.notified = True
            elif event.kind == "resolved" and alert.notified:
                dispatch_alert(
                    f"[AquasManager] {aquarium} — {alert.label} "
                    + ("de nouveau active" if stale else "revenue dans la cible"),
                    _describe(alert, event.value),
                    priority="low",
                )
        elif event.kind == "opened" and not _in_cooldown(event):
            grouped.append(f"{aquarium} — {_describe(alert, event.value)}")
            alert.notified = True

    if grouped:
        title = "[AquasManager] Nouvelle alerte" if len(grouped) == 1 else f"[AquasManager] {len(grouped)} nouvelles alertes"
        dispatch_alert(title, "\n".join(f"• {line}" for line in grouped), priority="default")
    db.commit()
