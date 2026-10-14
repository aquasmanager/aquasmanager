from tests.helpers import equipment_payload, pin_state


def test_equipment_pin_must_belong_to_controller(api, aquarium, controller, uid):
    other = api.post(
        "/controllers/", {"name": f"esp-autre-{uid}", "type": "ESP32", "zone": "x", "ip": f"192.168.2.{uid}"}, code=201
    )
    other_pin = api.get(f"/controllers/{other['id']}/pins")["controller_pins"][0]["id"]
    payload = equipment_payload(aquarium, controller, "12", f"Pompe {uid}")
    payload["pin_id"] = other_pin
    api.post("/equipments/", payload, code=400)


def test_equipment_inversion_and_busy_pin(api, aquarium, controller, uid):
    nc = api.post("/equipments/", equipment_payload(aquarium, controller, "12", f"Pompe {uid}", physical_contact="NC"), code=201)
    assert nc["inverted"] is True  # déduit du contact NC
    # Broche renvoyée pour l'affichage (liste et détail)
    assert nc["pin_number"] == "12" and nc["module_id"] is None
    listed = next(e for e in api.get("/equipments/")["equipments"] if e["id"] == nc["id"])
    assert listed["pin_number"] == "12"
    chosen = api.post("/equipments/", equipment_payload(aquarium, controller, "13", f"Chauffage {uid}", inverted=True), code=201)
    assert chosen["inverted"] is True  # choix explicite respecté
    assert pin_state(controller["pins"]["12"]) == ("OUT", "GPIO", f"Pompe {uid}")
    api.post("/equipments/", equipment_payload(aquarium, controller, "12", f"Ecumeur {uid}"), code=409)


def test_mode_change_keeps_controller_dirty(api, aquarium, controller, uid):
    eq = api.post("/equipments/", equipment_payload(aquarium, controller, "14", f"Remontee {uid}"), code=201)
    api.post(f"/controllers/{controller['id']}/sync_success")
    api.patch(f"/equipments/{eq['id']}", {"restart_delay": 5})
    api.patch(f"/equipments/{eq['id']}/mode", {"mode": "MANUAL"})
    assert api.get(f"/controllers/{controller['id']}")["is_dirty"] is True


def test_equipment_move_releases_old_pin(api, aquarium, controller, uid):
    eq = api.post("/equipments/", equipment_payload(aquarium, controller, "15", f"Brassage {uid}"), code=201)
    pins = api.get(f"/controllers/{controller['id']}/pins", params={"include_pin_id": controller["pins"]["15"]})
    assert any(p["id"] == controller["pins"]["15"] for p in pins["controller_pins"])

    moved = api.patch(f"/equipments/{eq['id']}", {"pin_id": controller["pins"]["18"], "name": f"Brassage gauche {uid}", "status": "ON"})
    # Nom technique « <nom>_<aquarium> », le firmware flashé garde l'ancien nom jusqu'au flash
    assert moved["technical_name"] == f"brassage_gauche_{uid}_bac_test_{uid}"
    assert moved["status"] == "OFF"  # l'état réel vient du contrôleur, pas du formulaire
    assert pin_state(controller["pins"]["15"])[0] == "FREE"
    assert pin_state(controller["pins"]["18"]) == ("OUT", "GPIO", f"Brassage gauche {uid}")


def test_rename_to_existing_name_is_refused(api, aquarium, controller, uid):
    api.post("/equipments/", equipment_payload(aquarium, controller, "19", f"Osmo {uid}"), code=201)
    other = api.post("/equipments/", equipment_payload(aquarium, controller, "21", f"Osmoseur {uid}"), code=201)
    api.patch(f"/equipments/{other['id']}", {"name": f"Osmo {uid}"}, code=400)


def test_sensor_units_and_shared_one_wire_bus(api, aquarium, controller, uid):
    base = {"aquarium_id": aquarium["id"], "controller_id": controller["id"], "type": "sensor"}
    t1 = api.post("/sensors/", {**base, "name": f"Temp A {uid}", "pin_id": controller["pins"]["4"], "unit": "temperature",
                                "address": "0x1c0000031edd2a28"}, code=201)
    t2 = api.post("/sensors/", {**base, "name": f"Temp B {uid}", "pin_id": controller["pins"]["4"], "unit": "temperature",
                                "address": "0x2c0000031edd2a28"}, code=201)
    level = api.post("/sensors/", {**base, "name": f"Niveau {uid}", "pin_id": controller["pins"]["25"], "unit": "niveau"}, code=201)
    assert t1["unit"] == "°C" and level["unit"] == "level" and level["type"] == "binary_sensor"
    api.post("/sensors/", {**base, "name": f"pH {uid}", "pin_id": controller["pins"]["26"], "unit": "ph"}, code=422)

    # L'unité du formulaire (« temperature ») reste stockée « °C »
    edited = api.patch(f"/sensors/{t1['id']}", {"unit": "temperature", "name": f"Temp bac {uid}"})
    assert edited["unit"] == "°C"

    # Retirer une sonde du bus ne libère pas la broche tant qu'une autre l'utilise
    api.delete(f"/sensors/{t2['id']}")
    assert pin_state(controller["pins"]["4"])[1] == "1WIRE"

    api.patch(f"/sensors/{level['id']}", {"pin_id": controller["pins"]["27"]})
    assert pin_state(controller["pins"]["25"])[0] == "FREE"
    assert pin_state(controller["pins"]["27"]) == ("IN", "GPIO", f"Niveau {uid}")


def test_controller_rename_requires_reflash(api, controller):
    api.post(f"/controllers/{controller['id']}/sync_success")
    renamed = api.patch(f"/controllers/{controller['id']}", {"name": f"{controller['name']}-bis"})
    assert renamed["technical_name"].endswith("-bis") or renamed["technical_name"].endswith("_bis")
    assert renamed["is_dirty"] is True


def test_same_name_allowed_in_another_aquarium(api, aquarium, controller, uid):
    other_aq = api.post("/aquariums/", {"name": f"Bac bis {uid}", "volume": 100, "water_type": "sea",
                                        "biotope": "récifal", "date_creation": "2026-01-01"}, code=201)
    base = {"controller_id": controller["id"], "type": "sensor", "unit": "temperature", "pin_id": controller["pins"]["4"]}
    first = api.post("/sensors/", {**base, "aquarium_id": aquarium["id"], "name": "Température",
                                   "address": f"0x3c{uid:06x}1edd2a28"}, code=201)
    second = api.post("/sensors/", {**base, "aquarium_id": other_aq["id"], "name": "Température",
                                    "address": f"0x4c{uid:06x}1edd2a28"}, code=201)
    # Même nom affiché, noms techniques (MQTT, firmware) distincts
    assert first["name"] == second["name"] == "Température"
    assert first["technical_name"] != second["technical_name"]
    assert second["technical_name"].startswith(first["technical_name"].split("_")[0])
    # Dans le même aquarium : refusé, y compris pour un équipement du même nom
    api.post("/sensors/", {**base, "aquarium_id": aquarium["id"], "name": "température",
                           "address": f"0x5c{uid:06x}1edd2a28"}, code=400)
    api.post("/equipments/", equipment_payload(aquarium, controller, "22", "Température"), code=400)
    eq = api.post("/equipments/", equipment_payload(other_aq, controller, "23", f"Pompe {uid}"), code=201)
    api.post("/equipments/", equipment_payload(aquarium, controller, "25", f"Pompe {uid}"), code=201)
    # Déplacer un équipement vers un aquarium où son nom existe déjà : refusé
    moved = api.post("/equipments/", equipment_payload(other_aq, controller, "26", "Température"), code=400)
    assert moved["detail"]
    api.patch(f"/equipments/{eq['id']}", {"aquarium_id": aquarium["id"]}, code=400)
