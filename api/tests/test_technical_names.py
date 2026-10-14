from middleware.database import SessionLocal
from models.equipment import Equipment
from models.sensor import Sensor
from services.technical_names import base_name, firmware_name
from tests.helpers import equipment_payload


def test_base_name_format():
    assert base_name("Osmolateur", "Récif") == "osmolateur_recif"
    assert base_name("Pompe de remontée", "Bac Principal") == "pompe_de_remonte_bac_principal"  # 30 car. max
    assert base_name("Osmolateur récif", "Récif") == "osmolateur_recif"  # pas de doublon
    long = base_name("Pompe de brassage gauche arrière", "Récif du salon principal")
    assert len(long) <= 30 and long == "pompe_de_brassage_gau_recif_du" and long.startswith("pompe_de_brassage")
    assert base_name("2e pompe", "Récif") == "e_2e_pompe_recif"  # identifiant firmware : une lettre d'abord
    assert base_name("Chauffage", None) == "chauffage"


def test_two_aquariums_get_readable_names(api, controller, uid):
    bacs = [api.post("/aquariums/", {"name": f"{n} {uid}", "volume": 100, "water_type": "sea", "biotope": "récifal",
                                     "date_creation": "2026-01-01"}, code=201) for n in ("Récif", "Nano")]
    first = api.post("/equipments/", equipment_payload(bacs[0], controller, "25", "Osmolateur"), code=201)
    second = api.post("/equipments/", equipment_payload(bacs[1], controller, "26", "Osmolateur"), code=201)
    assert first["technical_name"] == f"osmolateur_recif_{uid}"
    assert second["technical_name"] == f"osmolateur_nano_{uid}"
    sensor = api.post("/sensors/", {"aquarium_id": bacs[0]["id"], "controller_id": controller["id"], "type": "binary_sensor",
                                    "unit": "level", "name": "Niveau décante", "pin_id": controller["pins"]["27"]}, code=201)
    assert sensor["technical_name"] == f"niveau_decante_recif_{uid}"


def test_rename_keeps_flashed_name_until_next_flash(api, aquarium, controller, uid):
    eq = api.post("/equipments/", equipment_payload(aquarium, controller, "32", f"Pompe {uid}"), code=201)
    old = eq["technical_name"]
    api.post(f"/controllers/{controller['id']}/sync_success", {})

    renamed = api.patch(f"/equipments/{eq['id']}", {"name": f"Remontée {uid}"})
    assert renamed["technical_name"] == f"remontee_{uid}_bac_test_{uid}"
    db = SessionLocal()
    try:
        row = db.get(Equipment, eq["id"])
        assert row.deployed_technical_name == old and firmware_name(row) == old
    finally:
        db.close()

    # Renommage de l'aquarium : recalculé, l'ancien nom flashé reste celui du firmware
    api.patch(f"/aquariums/{aquarium['id']}", {"name": f"Récif {uid}"})
    db = SessionLocal()
    try:
        row = db.get(Equipment, eq["id"])
        assert row.technical_name == f"remontee_{uid}_recif_{uid}" and row.deployed_technical_name == old
    finally:
        db.close()
    assert api.get(f"/controllers/{controller['id']}")["is_dirty"] is True

    # Flash confirmé : le firmware connaît désormais le nouveau nom
    api.post(f"/controllers/{controller['id']}/sync_success", {})
    db = SessionLocal()
    try:
        row = db.get(Equipment, eq["id"])
        assert row.deployed_technical_name is None and firmware_name(row) == row.technical_name
    finally:
        db.close()


def test_mqtt_messages_found_by_flashed_name(api, aquarium, controller, uid):
    import drivers.mqtt as mqtt

    sensor = api.post("/sensors/", {"aquarium_id": aquarium["id"], "controller_id": controller["id"], "type": "binary_sensor",
                                    "unit": "level", "name": f"Flotteur {uid}", "pin_id": controller["pins"]["33"]}, code=201)
    api.post(f"/controllers/{controller['id']}/sync_success", {})
    api.patch(f"/sensors/{sensor['id']}", {"name": f"Niveau {uid}"})
    db = SessionLocal()
    try:
        flashed = db.get(Sensor, sensor["id"]).deployed_technical_name
        ctrl = api.get(f"/controllers/{controller['id']}")
        sensor_id, _ = mqtt.mqtt_driver._save_sensor_reading(db, ctrl["technical_name"], flashed, 1.0)
        assert sensor_id == sensor["id"]
    finally:
        db.close()
