from middleware.database import SessionLocal
from models.fault import EquipmentFault
from models.metric_alert import MetricAlert, MetricAlertSource
from tests.helpers import equipment_payload


def test_overview_lists_open_alerts(api, aquarium, controller, uid):
    pump = api.post("/equipments/", equipment_payload(aquarium, controller, "12", f"Pompe {uid}"), code=201)
    with SessionLocal() as db:
        db.add(MetricAlert(aquarium_id=aquarium["id"], source=MetricAlertSource.water_parameter, label=f"KH {uid}",
                           unit="dKH", initial_value=5.1, target_min=7, target_max=9))
        # Déjà dans les tâches / le stock de « À faire » : pas répétée dans les alertes
        db.add(MetricAlert(aquarium_id=aquarium["id"], source=MetricAlertSource.task_overdue, label=f"Tâche {uid}",
                           initial_value=3))
        db.add(EquipmentFault(controller_id=controller["id"], equipment_id=pump["id"], code="LEVEL_TIMEOUT",
                              message="Niveau non atteint", latched=True))
        db.commit()

    alerts = [a for a in api.get("/overview/")["todo"]["alerts"] if a.get("aquarium_id") == aquarium["id"]]
    metric = [a for a in alerts if a["kind"] == "metric"]
    faults = [a for a in alerts if a["kind"] == "fault"]
    assert [a["label"] for a in metric] == [f"KH {uid}"] and metric[0]["aquarium_name"] == aquarium["name"]
    assert faults[0]["code"] == "LEVEL_TIMEOUT" and faults[0]["equipment_name"] == f"Pompe {uid}"
