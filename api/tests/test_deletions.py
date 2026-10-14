import os

from middleware.database import SessionLocal
from models.fault import EquipmentFault
from models.inventory import InventoryItem
from models.maintenance_task import MaintenanceTask
from models.photo import Photo
from models.rule import Rule
from models.water_parameter import WaterParameter
from tests.helpers import equipment_payload, pin_state

FISH = {"scientific_name": "Amphiprion ocellaris", "family": "Pomacentridae", "origin": "Indo-Pacifique",
        "max_height": 8, "min_volume": 100, "reef_safe": True, "date_acquisition": "2026-01-01"}


def test_rule_without_conditions_and_orphan_faults_are_removed(api, aquarium, controller, uid):
    heater = api.post("/equipments/", equipment_payload(aquarium, controller, "12", f"Chauffe {uid}"), code=201)
    level = api.post("/sensors/", {"aquarium_id": aquarium["id"], "controller_id": controller["id"], "type": "sensor",
                                   "name": f"Flotteur {uid}", "pin_id": controller["pins"]["25"], "unit": "niveau"}, code=201)
    rule = api.post("/rules/", {"name": f"Regle {uid}", "action": "ON", "match_type": "AND", "is_active": True,
                                "equipment_id": heater["id"],
                                "conditions": [{"sensor_id": level["id"], "condition_type": "SENSOR_STATE", "trigger_state": "LOW"}]},
                    code=201)
    db = SessionLocal()
    db.add(EquipmentFault(controller_id=controller["id"], equipment_id=heater["id"], code="LEVEL_TIMEOUT", message="t", latched=True))
    db.commit()
    db.close()

    api.delete(f"/sensors/{level['id']}")
    api.delete(f"/equipments/{heater['id']}")

    db = SessionLocal()
    try:
        assert db.get(Rule, rule["id"]) is None
        assert db.query(EquipmentFault).filter(EquipmentFault.equipment_id == heater["id"]).count() == 0
    finally:
        db.close()
    assert pin_state(controller["pins"]["12"])[0] == "FREE"


def test_livestock_photos_are_deleted_with_the_item(api, client, admin_headers, aquarium, uid):
    fish = api.post("/fishes/", {"aquarium_id": aquarium["id"], "name": f"Clown {uid}", **FISH}, code=201)
    response = client.post(f"/photos/fishes/{fish['id']}", files={"file": ("a.jpg", b"img", "image/jpeg")}, headers=admin_headers)
    assert response.status_code == 200
    api.delete(f"/fishes/{fish['id']}")
    db = SessionLocal()
    try:
        assert db.query(Photo).filter(Photo.entity_type == "fishes", Photo.entity_id == fish["id"]).count() == 0
    finally:
        db.close()
    assert not os.path.exists(f"uploads/fishes/{fish['id']}")


def test_aquarium_deletion_removes_everything(api, aquarium, controller, uid):
    api.post("/equipments/", equipment_payload(aquarium, controller, "13", f"Pompe {uid}"), code=201)
    api.post("/sensors/", {"aquarium_id": aquarium["id"], "controller_id": controller["id"], "type": "sensor",
                           "name": f"Temp {uid}", "pin_id": controller["pins"]["4"], "unit": "temperature"}, code=201)
    api.post("/fishes/", {"aquarium_id": aquarium["id"], "name": f"Chirurgien {uid}", **FISH}, code=201)
    api.post("/water-parameters/", {"aquarium_id": aquarium["id"], "name": "KH", "unit": "dKH"}, code=201)
    api.post("/maintenance-tasks/", {"aquarium_id": aquarium["id"], "title": "Résine", "recurrence": "none"}, code=201)
    api.post("/inventory-items/", {"aquarium_id": aquarium["id"], "name": "Sel", "unit": "kg", "quantity": 2}, code=201)
    api.post(f"/controllers/{controller['id']}/sync_success")

    api.delete(f"/aquariums/{aquarium['id']}")

    assert pin_state(controller["pins"]["13"])[0] == "FREE"
    assert pin_state(controller["pins"]["4"])[0] == "FREE"
    assert api.get(f"/controllers/{controller['id']}")["is_dirty"] is True
    db = SessionLocal()
    try:
        for model in (WaterParameter, MaintenanceTask, InventoryItem):
            assert db.query(model).filter(model.aquarium_id == aquarium["id"]).count() == 0
    finally:
        db.close()


def test_coral_cites_is_optional(api, aquarium):
    coral = api.post("/corals/", {"aquarium_id": aquarium["id"], "name": "Euphyllia", "type": "LPS",
                                  "scientific_name": "Euphyllia ancora", "family": "Euphylliidae", "origin": "Indonésie",
                                  "light_range": {"min": 3, "max": 6}, "brewing_range": {"min": 3, "max": 6},
                                  "aggressiveness_level": 5, "resistance_level": 5, "location_level": 5,
                                  "date_acquisition": "2026-01-01"}, code=201)
    assert coral["cites"] == ""
