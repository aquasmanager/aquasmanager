from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from middleware.database import SessionLocal
from models.maintenance_task import MaintenanceTask
from models.sensor_reading import SensorReading
from services import notify
from services.maintenance_task import days_overdue, is_overdue
from services.retention import purge_old_sensor_readings
from services.task_reminders import send_due_today_reminders

PARIS = ZoneInfo("Europe/Paris")


def test_overdue_only_from_next_morning():
    due = datetime(2026, 9, 24, 12, 0)  # échéance saisie « le 24 » (midi)
    assert not is_overdue(due, datetime(2026, 9, 24, 20, 0, tzinfo=PARIS))
    assert not is_overdue(due, datetime(2026, 9, 25, 7, 0, tzinfo=PARIS))  # avant l'heure du rappel
    assert is_overdue(due, datetime(2026, 9, 25, 9, 0, tzinfo=PARIS))
    assert days_overdue(due, datetime(2026, 9, 27, 9, 0, tzinfo=PARIS)) == 3


def test_due_today_reminder_sent_once(api, aquarium, monkeypatch, uid):
    sent = []
    monkeypatch.setattr(notify, "dispatch_alert", lambda subject, message, priority="default": sent.append((subject, message)))
    task = api.post("/maintenance-tasks/", {"aquarium_id": aquarium["id"], "title": f"Changement d'eau {uid}",
                                            "recurrence": "weekly", "next_due_at": "2030-03-14T12:00:00"}, code=201)

    assert send_due_today_reminders(SessionLocal(), datetime(2030, 3, 14, 7, 0, tzinfo=PARIS)) == 0  # trop tôt
    db = SessionLocal()
    try:
        assert send_due_today_reminders(db, datetime(2030, 3, 14, 8, 5, tzinfo=PARIS)) >= 1
        assert send_due_today_reminders(db, datetime(2030, 3, 14, 9, 0, tzinfo=PARIS)) == 0  # déjà rappelée
        assert db.get(MaintenanceTask, task["id"]).reminder_sent_on.isoformat() == "2030-03-14"
    finally:
        db.close()
    assert any(f"Changement d'eau {uid}" in message and aquarium["name"] in message for _, message in sent)


def test_sensor_readings_retention(api, aquarium, controller, uid):
    sensor = api.post("/sensors/", {"aquarium_id": aquarium["id"], "controller_id": controller["id"], "type": "sensor",
                                    "name": f"Temp purge {uid}", "pin_id": controller["pins"]["4"], "unit": "temperature"}, code=201)
    db = SessionLocal()
    try:
        db.add(SensorReading(sensor_id=sensor["id"], value=24.0, timestamp=datetime.now() - timedelta(days=400)))
        db.add(SensorReading(sensor_id=sensor["id"], value=25.0, timestamp=datetime.now() - timedelta(days=10)))
        db.commit()
        assert purge_old_sensor_readings(db, 0) == 0  # 0 = illimité
        assert purge_old_sensor_readings(db, 365) >= 1
        remaining = [r.value for r in db.query(SensorReading).filter(SensorReading.sensor_id == sensor["id"])]
        assert remaining == [25.0]
    finally:
        db.close()
