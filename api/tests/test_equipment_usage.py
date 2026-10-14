from datetime import datetime, timedelta

from middleware.database import SessionLocal
from models.equipment_activation import EquipmentActivation
from models.maintenance_task import MaintenanceTask
from services.equipment_usage import check_service_due, record_runtime
from tests.helpers import equipment_payload


def test_usage_hours_energy_and_service(api, aquarium, controller, uid):
    equipment = api.post("/equipments/", equipment_payload(aquarium, controller, "12", f"UV {uid}"), code=201)
    now = datetime.now()
    db = SessionLocal()
    try:
        # Historique existant : 100 h il y a longtemps + 10 h ces 30 derniers jours, puis allumé depuis 2 h
        db.add(EquipmentActivation(equipment_id=equipment["id"], started_at=now - timedelta(days=200),
                                   ended_at=now - timedelta(days=200) + timedelta(hours=100), duration_seconds=100 * 3600))
        db.add(EquipmentActivation(equipment_id=equipment["id"], started_at=now - timedelta(days=5),
                                   ended_at=now - timedelta(days=5) + timedelta(hours=10), duration_seconds=10 * 3600))
        db.add(EquipmentActivation(equipment_id=equipment["id"], started_at=now - timedelta(hours=2)))
        db.commit()
    finally:
        db.close()

    api.put("/equipment-usage/settings", {"price_per_kwh": 0.25})
    row = api.put(f"/equipment-usage/{equipment['id']}", {"power_watts": 36, "service_interval_hours": 100,
                                                          "service_label": "Remplacer l'ampoule UV"})
    assert row["hours_total"] == 112.0 and row["hours_30d"] == 12.0 and row["running"]
    assert row["kwh_30d"] == round(36 * 12 / 1000, 2) and row["cost_30d"] == round(36 * 12 / 1000 * 0.25, 2)
    assert row["service_progress"] > 1

    # Entretien dépassé : une seule tâche créée
    db = SessionLocal()
    try:
        assert check_service_due(db) >= 1
        assert check_service_due(db) == 0
        assert db.query(MaintenanceTask).filter(MaintenanceTask.title == f"Remplacer l'ampoule UV : UV {uid}").count() == 1
        # Activation terminée par le driver : ajoutée au compteur cumulé
        record_runtime(db, equipment["id"], 3600)
        db.commit()
    finally:
        db.close()

    row = api.post(f"/equipment-usage/{equipment['id']}/serviced")
    assert row["hours_since_service"] < 0.1 and row["hours_total"] == 113.0 and row["serviced_at"]
