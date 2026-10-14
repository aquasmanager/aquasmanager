from datetime import datetime, timedelta

from middleware.database import SessionLocal
from models.aquarium import Aquarium
from services import maintenance
from tests.helpers import equipment_payload


def _modes(api, ids):
    return {i: api.get(f"/equipments/{i}")["mode"] for i in ids}


def test_maintenance_stops_then_restores_equipment(api, aquarium, controller, uid):
    pump = api.post("/equipments/", equipment_payload(aquarium, controller, "12", f"Brassage {uid}"), code=201)
    heater = api.post("/equipments/", equipment_payload(aquarium, controller, "13", f"Chauffage {uid}"), code=201)
    light_pump = api.post("/equipments/", equipment_payload(aquarium, controller, "14", f"Remontée {uid}"), code=201)
    api.patch(f"/equipments/{heater['id']}/mode", {"mode": "MANUAL"})

    state = api.get(f"/aquariums/{aquarium['id']}/maintenance")
    assert state["active"] is False
    assert set(state["equipment_ids"]) == {pump["id"], heater["id"], light_pump["id"]}  # première fois : tout

    state = api.post(f"/aquariums/{aquarium['id']}/maintenance",
                     {"equipment_ids": [pump["id"], heater["id"]], "minutes": 30})
    assert state["active"] is True and state["equipment_ids"] == [pump["id"], heater["id"]]
    assert _modes(api, [pump["id"], heater["id"], light_pump["id"]]) == {
        pump["id"]: "MANUAL", heater["id"]: "MANUAL", light_pump["id"]: "AUTO"}
    with SessionLocal() as db:
        assert aquarium["id"] in maintenance.paused_aquarium_ids(db)

    state = api.delete(f"/aquariums/{aquarium['id']}/maintenance", code=200)
    assert state["active"] is False
    # Mode d'avant retrouvé ; sélection gardée pour la prochaine fois
    assert _modes(api, [pump["id"], heater["id"]]) == {pump["id"]: "AUTO", heater["id"]: "MANUAL"}
    assert api.get(f"/aquariums/{aquarium['id']}/maintenance")["equipment_ids"] == [pump["id"], heater["id"]]


def test_maintenance_ends_by_itself(api, aquarium, controller, uid):
    pump = api.post("/equipments/", equipment_payload(aquarium, controller, "12", f"Pompe {uid}"), code=201)
    api.post(f"/aquariums/{aquarium['id']}/maintenance", {"equipment_ids": [pump["id"]], "minutes": 60})
    with SessionLocal() as db:
        db.get(Aquarium, aquarium["id"]).maintenance_until = datetime.now() - timedelta(seconds=1)
        db.commit()
        assert aquarium["name"] in maintenance.expire_due(db)
    assert api.get(f"/equipments/{pump['id']}")["mode"] == "AUTO"
    assert api.get(f"/aquariums/{aquarium['id']}/maintenance")["active"] is False


def test_maintenance_refuses_other_aquarium_equipment(api, aquarium, controller, uid):
    other = api.post("/aquariums/", {"name": f"Autre {uid}", "volume": 60, "water_type": "pure", "biotope": "Asiatique",
                                     "date_creation": "2026-01-01"}, code=201)
    foreign = api.post("/equipments/", equipment_payload(other, controller, "12", f"Filtre {uid}"), code=201)
    api.post(f"/aquariums/{aquarium['id']}/maintenance", {"equipment_ids": [foreign["id"]], "minutes": 30}, code=400)
