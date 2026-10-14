from services.one_wire_scan import parse_i2c_scan
from tests.helpers import equipment_payload


def test_modules_are_numbered_editable_and_protected(api, aquarium, controller, uid):
    cid = controller["id"]
    api.post(f"/controllers/{cid}/modules", {"address": "0x20", "type": "PCF8574"})
    api.post(f"/controllers/{cid}/modules", {"address": "0X21", "type": "PCF8574"})
    modules = api.get(f"/controllers/{cid}/modules")
    assert [(m["number"], m["address"]) for m in modules] == [(1, "0x20"), (2, "0x21")]
    api.post(f"/controllers/{cid}/modules", {"address": "0x21", "type": "PCF8574"}, code=409)

    # Renuméroter / changer d'adresse : garde les broches
    api.patch(f"/controllers/{cid}/modules/0x21", {"number": 1}, code=409)
    moved = api.patch(f"/controllers/{cid}/modules/0x21", {"number": 3, "address": "0x22"})
    assert moved["number"] == 3 and moved["address"] == "0x22"

    # Un équipement sur le module : suppression refusée ; numéro visible sur l'équipement
    pins = api.get(f"/controllers/{cid}/pins")["controller_pins"]
    pin = next(p for p in pins if p["module_number"] == 3 and p["pin_number"] == "2")
    payload = {**equipment_payload(aquarium, controller, "15", f"Relais {uid}"), "pin_id": pin["id"]}
    eq = api.post("/equipments/", payload, code=201)
    assert eq["module_number"] == 3
    api.delete(f"/controllers/{cid}/modules/0x22", code=409)
    api.patch(f"/controllers/{cid}/modules/0x22", {"type": "PCF8575"})
    assert len([p for p in api.get(f"/controllers/{cid}/pins")["controller_pins"] if p["module_number"] == 3]) == 15
    api.delete(f"/equipments/{eq['id']}", code=204)
    api.delete(f"/controllers/{cid}/modules/0x22", code=204)
    api.delete(f"/controllers/{cid}/modules/0x20", code=204)
    assert api.get(f"/controllers/{cid}/modules") == []


def test_parse_i2c_scan():
    messages = [
        "\x1b[0;35m[C][i2c.idf:096]: I2C Bus:\n  SDA Pin: GPIO21\n  SCL Pin: GPIO22\x1b[0m",
        "[C][i2c.idf:109]: Results from bus scan:",
        "[C][i2c.idf:115]: Found device at address 0x20",
        "[C][i2c.idf:115]: Found device at address 0x68",
        "[C][i2c.idf:115]: Found device at address 0x57",
        "[C][gpio.one_wire:087]: Found device at address 0x99",
    ]
    assert parse_i2c_scan(messages) == {"enabled": True, "addresses": ["0x20", "0x57", "0x68"]}
    assert parse_i2c_scan(["[C][wifi:123]: SSID: x"]) == {"enabled": False, "addresses": []}


def test_parse_one_wire_scan_diagnostics():
    from services.one_wire_scan import parse_one_wire_scan

    with_probes = [
        "[C][wifi:123]: SSID: x",
        "[C][gpio.one_wire:020]: GPIO 1-wire bus:\n  Pin: GPIO4",
        "[C][gpio.one_wire:087]:   Found devices:",
        "[C][gpio.one_wire:090]:     0x2801234567890abc (DS18B20)",
    ]
    result = parse_one_wire_scan(with_probes)
    assert result["buses"] == [{"pin_number": 4, "devices": 1}]
    assert result["devices"][0] == {"address": "0x2801234567890abc", "model": "DS18B20", "pin_number": 4}
    # Bus présent, aucune sonde ne répond (câblage)
    empty = parse_one_wire_scan(with_probes[:2] + ["[W][gpio.one_wire:085]:   Found no devices!"])
    assert empty["buses"] == [{"pin_number": 4, "devices": 0}] and empty["devices"] == []
    # Pas de bus dans le firmware / rien reçu
    assert parse_one_wire_scan(with_probes[:1]) == {"config_received": True, "buses": [], "devices": []}
    assert parse_one_wire_scan([])["config_received"] is False


def test_i2c_frequency_setting(api, controller):
    from middleware.database import SessionLocal
    from models.controller import Controller
    from services.esphome_generator import generate_esphome_yaml

    cid = controller["id"]
    api.post(f"/controllers/{cid}/modules", {"address": "0x20", "type": "PCF8574"})
    assert api.get(f"/controllers/{cid}")["i2c_frequency_khz"] == 50
    api.post(f"/controllers/{cid}/sync_success", {})
    updated = api.patch(f"/controllers/{cid}", {"i2c_frequency_khz": 10})
    assert updated["i2c_frequency_khz"] == 10 and updated["is_dirty"] is True
    api.patch(f"/controllers/{cid}", {"i2c_frequency_khz": 33}, code=422)
    db = SessionLocal()
    try:
        assert "frequency: 10kHz" in generate_esphome_yaml(db.get(Controller, cid))
    finally:
        db.close()


def test_restart_controller_needs_restart_capable_firmware(api, controller, monkeypatch):
    from drivers.mqtt import mqtt_driver

    sent = []
    monkeypatch.setattr(mqtt_driver, "publish", lambda topic, payload, **kw: sent.append((topic, payload)))
    cid = controller["id"]
    api.post(f"/controllers/{cid}/restart", {}, code=409)  # jamais flashé avec le bouton
    api.post(f"/controllers/{cid}/sync_success", {})
    assert api.post(f"/controllers/{cid}/restart", {}) == {"status": "sent"}
    assert sent == [(f"{controller['technical_name']}/button/restart/command", "PRESS")]


def test_one_wire_scan_attributes_unaddressed_probe_alone_on_its_pin(api, aquarium, controller, monkeypatch, uid):
    import routes.controller as ctrl_routes

    cid = controller["id"]
    api.patch(f"/controllers/{cid}", {"ip": "192.0.2.50"})
    base = {"aquarium_id": aquarium["id"], "controller_id": cid, "type": "sensor", "unit": "temperature"}
    alone = api.post("/sensors/", {**base, "name": f"Bouture {uid}", "pin_id": controller["pins"]["13"]}, code=201)
    addressed = api.post("/sensors/", {**base, "name": f"Récif {uid}", "pin_id": controller["pins"]["4"],
                                       "address": "0x28AA00000000000B"}, code=201)

    async def fake_scan(ip):
        return {"config_received": True,
                "buses": [{"pin_number": 13, "devices": 1}, {"pin_number": 4, "devices": 2}],
                "devices": [{"address": "0x28cc00000000000d", "model": "DS18B20", "pin_number": 13},
                            {"address": "0x28aa00000000000b", "model": "DS18B20", "pin_number": 4},
                            {"address": "0x28ee00000000000f", "model": "DS18B20", "pin_number": 4}]}

    monkeypatch.setattr(ctrl_routes, "scan_one_wire_devices", fake_scan)
    devices = {d["address"]: d for d in api.get(f"/controllers/{cid}/one-wire/scan")["devices"]}
    assert devices["0x28cc00000000000d"]["sensor_id"] == alone["id"]
    assert devices["0x28aa00000000000b"]["sensor_id"] == addressed["id"]
    assert devices["0x28ee00000000000f"]["sensor_id"] is None


def test_pins_include_used_with_owner(api, aquarium, controller, uid):
    from tests.helpers import equipment_payload

    cid = controller["id"]
    api.post(f"/controllers/{cid}/modules", {"address": "0x25", "type": "PCF8574"})
    pins = api.get(f"/controllers/{cid}/pins")["controller_pins"]
    pin0 = next(p for p in pins if p["module_number"] and p["pin_number"] == "0")
    api.post("/equipments/", {**equipment_payload(aquarium, controller, "15", f"Écumeur {uid}"), "pin_id": pin0["id"]}, code=201)

    free_only = api.get(f"/controllers/{cid}/pins")["controller_pins"]
    assert all(p["id"] != pin0["id"] for p in free_only)
    every = {p["id"]: p for p in api.get(f"/controllers/{cid}/pins", params={"include_used": True})["controller_pins"]}
    assert every[pin0["id"]]["free"] is False
    assert every[pin0["id"]]["used_by"] == f"Écumeur {uid} · {aquarium['name']}"


def test_pins_explain_one_wire_bus_and_i2c(api, aquarium, controller, uid):
    from tests.helpers import equipment_payload

    cid = controller["id"]
    base = {"aquarium_id": aquarium["id"], "controller_id": cid, "type": "sensor", "unit": "temperature",
            "pin_id": controller["pins"]["4"]}
    api.post("/sensors/", {**base, "name": f"Temp A {uid}", "address": "0x28aa00000000000b"}, code=201)
    api.post("/sensors/", {**base, "name": f"Temp B {uid}", "address": "0x28bb00000000000c"}, code=201)

    # GPIO 21 libre tant qu'il n'y a ni horloge ni module
    pins = {p["pin_number"]: p for p in api.get(f"/controllers/{cid}/pins", params={"include_used": True})["controller_pins"]
            if p["module_id"] is None}
    assert pins["21"]["free"] is True
    gpio4 = pins["4"]
    assert gpio4["one_wire"] is True and gpio4["free"] is False
    assert gpio4["used_by"] == f"Bus 1-Wire : Temp A {uid} · {aquarium['name']}, Temp B {uid} · {aquarium['name']}"

    # Avec un module : GPIO 21 et 22 réservées au bus I2C, refusées pour un équipement
    api.post(f"/controllers/{cid}/modules", {"address": "0x26", "type": "PCF8574"})
    pins = {p["pin_number"]: p for p in api.get(f"/controllers/{cid}/pins", params={"include_used": True})["controller_pins"]
            if p["module_id"] is None}
    assert (pins["21"]["free"], pins["21"]["used_by"]) == (False, "Bus I2C (SDA)")
    assert pins["22"]["used_by"] == "Bus I2C (SCL)"
    free_only = {p["pin_number"] for p in api.get(f"/controllers/{cid}/pins")["controller_pins"] if p["module_id"] is None}
    assert "21" not in free_only and "4" in free_only  # bus 1-Wire encore proposé (sondes)
    api.post("/equipments/", equipment_payload(aquarium, controller, "21", f"Relais {uid}"), code=409)


def test_nan_reading_clears_last_value(api, aquarium, controller, uid, monkeypatch):
    import drivers.mqtt as mqtt
    from middleware.database import SessionLocal
    from models.sensor import Sensor

    sensor = api.post("/sensors/", {"aquarium_id": aquarium["id"], "controller_id": controller["id"], "type": "sensor",
                                    "unit": "temperature", "name": f"Temp nan {uid}", "pin_id": controller["pins"]["4"]},
                      code=201)
    sent = []
    monkeypatch.setattr(mqtt.mqtt_driver, "_broadcast_to_ws", sent.append)
    monkeypatch.setattr(mqtt.mqtt_driver, "db_session_factory", SessionLocal)
    topic = f"{mqtt.mqtt_driver.topic_prefix}/{controller['technical_name']}/sensor/{sensor['technical_name']}/state"

    class Msg:
        def __init__(self, payload):
            self.topic, self.payload = topic, payload.encode()

    mqtt.mqtt_driver.on_message(None, None, Msg("25.4"))
    mqtt.mqtt_driver.on_message(None, None, Msg("nan"))
    db = SessionLocal()
    try:
        assert db.get(Sensor, sensor["id"]).last_value is None
    finally:
        db.close()
    assert [m["value"] for m in sent if m.get("type") == "SENSOR_READING"] == [25.4, None]


def test_silent_probe_cleared_after_three_intervals(api, aquarium, controller, uid):
    from datetime import datetime, timedelta

    from middleware.database import SessionLocal
    from models.sensor import Sensor
    from services.sensor_staleness import clear_silent_probes

    base = {"aquarium_id": aquarium["id"], "controller_id": controller["id"], "type": "sensor", "unit": "temperature"}
    fresh = api.post("/sensors/", {**base, "name": f"Fraîche {uid}", "pin_id": controller["pins"]["4"],
                                   "address": "0x28aa00000000000b", "interval": 60}, code=201)
    silent = api.post("/sensors/", {**base, "name": f"Muette {uid}", "pin_id": controller["pins"]["4"],
                                    "address": "0x28bb00000000000c", "interval": 60}, code=201)
    level = api.post("/sensors/", {**base, "type": "binary_sensor", "unit": "level", "name": f"Flotteur {uid}",
                                   "pin_id": controller["pins"]["25"]}, code=201)
    now = datetime.now()
    db = SessionLocal()
    try:
        for sensor_id, age in ((fresh["id"], 120), (silent["id"], 200), (level["id"], 3600)):
            row = db.get(Sensor, sensor_id)
            row.last_value, row.last_reading_at = 25.0, now - timedelta(seconds=age)
        db.commit()
        sent = []
        assert clear_silent_probes(db, now=now, notify=sent.append) == [silent["id"]]  # 200 s > 3 × 60 s
        db.expire_all()
        assert db.get(Sensor, fresh["id"]).last_value == 25.0
        assert db.get(Sensor, silent["id"]).last_value is None
        assert db.get(Sensor, level["id"]).last_value == 25.0  # flotteur : publie au changement seulement
        assert sent == [{"type": "SENSOR_READING", "sensor_id": silent["id"], "value": None}]
    finally:
        db.close()


def test_pca9685_channels_drive_light_channels(api, aquarium, controller, uid):
    """PCA9685 : 16 canaux PWM pour les canaux de lampe ; refusés pour un relais ou un capteur."""
    import yaml

    from middleware.database import SessionLocal
    from models.controller import Controller
    from services.esphome_generator import generate_esphome_yaml
    from tests.helpers import equipment_payload

    cid = controller["id"]
    api.patch(f"/controllers/{cid}", {"rtc_model": "DS3231"})
    api.post(f"/controllers/{cid}/modules", {"address": "0x40", "type": "PCA9685"})
    api.post(f"/controllers/{cid}/modules", {"address": "0x21", "type": "PCF8575"})
    pins = api.get(f"/controllers/{cid}/pins", params={"include_used": True})["controller_pins"]
    pca = [p for p in pins if p["module_type"] == "PCA9685"]
    assert len(pca) == 16
    pca3 = next(p for p in pca if p["pin_number"] == "3")

    api.post("/equipments/", {**equipment_payload(aquarium, controller, "15", f"Relais pca {uid}"), "pin_id": pca3["id"]}, code=409)

    def config_now():
        db = SessionLocal()
        try:
            content = generate_esphome_yaml(db.get(Controller, cid))
        finally:
            db.close()
        loader = type("Loader", (yaml.SafeLoader,), {})
        loader.add_multi_constructor("!", lambda loader_, suffix, node: None)
        return yaml.load(content, Loader=loader)

    # Module déclaré sans canal branché : absent du firmware (sinon échec de compilation)
    assert "pca9685" not in config_now()
    light = api.post("/lights/", {"name": f"Rampe pca {uid}", "aquarium_id": aquarium["id"], "controller_id": cid,
                                  "pwm_frequency": 2000}, code=201)
    api.post(f"/lights/{light['id']}/channels", {"name": "Bleu", "pin_id": pca3["id"]}, code=201)

    db = SessionLocal()
    try:
        content = generate_esphome_yaml(db.get(Controller, cid))
    finally:
        db.close()
    loader = type("Loader", (yaml.SafeLoader,), {})
    loader.add_multi_constructor("!", lambda loader_, suffix, node: None)
    config = yaml.load(content, Loader=loader)
    assert config["pca9685"] == [{"id": "pca9685_0x40", "address": 0x40, "frequency": "1525Hz"}]  # 2000 Hz borné
    assert {"id": "pcf8574_0x21", "address": 0x21, "pcf8575": True} in config["pcf8574"]
    out = next(o for o in config["output"] if o.get("platform") == "pca9685")
    assert out["pca9685_id"] == "pca9685_0x40" and out["channel"] == 3
