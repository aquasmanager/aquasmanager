import yaml

from middleware.database import SessionLocal
from models.controller import Controller
from services.esphome_generator import generate_esphome_yaml
from tests.helpers import equipment_payload


def _time_rule(equipment_id, uid):
    return {
        "name": f"Pause nourrissage {uid}",
        "action": "OFF",
        "equipment_id": equipment_id,
        "revert_on_exit": True,
        "conditions": [{"condition_type": "TIME_RANGE", "start_time": "12:00", "end_time": "12:15"}],
    }


def test_time_rule_and_light_need_an_rtc(api, aquarium, controller, uid):
    pump = api.post("/equipments/", equipment_payload(aquarium, controller, "12", f"Brassage {uid}"), code=201)
    api.post("/rules/", _time_rule(pump["id"], uid), code=400)
    light = {"name": f"Rampe {uid}", "aquarium_id": aquarium["id"], "controller_id": controller["id"]}
    api.post("/lights/", light, code=400)

    api.patch(f"/controllers/{controller['id']}", {"rtc_model": "DS3231"})
    rule = api.post("/rules/", _time_rule(pump["id"], uid), code=201)
    assert rule["revert_on_exit"] is True
    created_light = api.post("/lights/", light, code=201)
    api.post(f"/lights/{created_light['id']}/channels", {"name": "Blanc", "pin_id": controller["pins"]["13"]}, code=201)

    # L'horloge ne peut plus être retirée tant qu'elle sert
    api.patch(f"/controllers/{controller['id']}", {"rtc_model": None}, code=409)


def test_time_range_start_and_end_must_differ(api, aquarium, controller, uid):
    pump = api.post("/equipments/", equipment_payload(aquarium, controller, "14", f"Pompe {uid}"), code=201)
    rule = _time_rule(pump["id"], uid)
    rule["conditions"][0]["end_time"] = "12:00"
    api.post("/rules/", rule, code=422)


def test_generated_firmware_is_valid_yaml(api, aquarium, controller, uid):
    api.patch(f"/controllers/{controller['id']}", {"rtc_model": "DS3231"})
    pump = api.post("/equipments/", equipment_payload(aquarium, controller, "15", f"Remontee {uid}"), code=201)
    api.post("/sensors/", {"aquarium_id": aquarium["id"], "controller_id": controller["id"], "type": "sensor",
                           "name": f"Temp {uid}", "pin_id": controller["pins"]["4"], "unit": "temperature"}, code=201)
    api.post("/rules/", _time_rule(pump["id"], uid), code=201)

    db = SessionLocal()
    try:
        content = generate_esphome_yaml(db.get(Controller, controller["id"]))
    finally:
        db.close()
    # Les tags ESPHome (!lambda, !secret) ne sont pas du YAML standard : on les accepte tels quels
    loader = type("Loader", (yaml.SafeLoader,), {})
    loader.add_multi_constructor("!", lambda loader_, suffix, node: None)
    config = yaml.load(content, Loader=loader)
    assert config["esphome"]["name"]
    assert any("rule_" in script["id"] for script in config.get("script", []))


def test_controller_config_masks_secrets_and_diffs(api, client, aquarium, controller, uid):
    listing = api.get("/controllers/")["controllers"]
    assert all("yaml_config" not in c for c in listing)

    config = api.get(f"/controllers/{controller['id']}/config")
    assert config["deployed"] is None and config["diff"] is None
    assert "password" in config["desired"]
    for line in config["desired"].splitlines():
        if "password:" in line:
            assert "••••••" in line

    # Après un flash réussi : identique, puis différence dès qu'un équipement change
    from middleware.database import SessionLocal
    from models.controller import Controller
    from services.esphome_generator import generate_esphome_yaml

    db = SessionLocal()
    try:
        ctrl = db.get(Controller, controller["id"])
        ctrl.last_config = generate_esphome_yaml(ctrl)
        db.commit()
    finally:
        db.close()
    assert api.get(f"/controllers/{controller['id']}/config")["identical"] is True
    api.post("/equipments/", equipment_payload(aquarium, controller, "18", f"Nouvelle pompe {uid}"), code=201)
    changed = api.get(f"/controllers/{controller['id']}/config")
    assert changed["identical"] is False and "nouvelle_pompe" in changed["diff"]


def test_protected_switch_publishes_state_immediately(api, aquarium, controller, uid):
    """Osmolateur : l'état public suit le relais sans attendre la relecture du template (60 s)."""
    osmo = api.post("/equipments/", equipment_payload(aquarium, controller, "15", f"Osmolateur {uid}"), code=201)
    db = SessionLocal()
    try:
        content = generate_esphome_yaml(db.get(Controller, controller["id"]))
    finally:
        db.close()
    loader = type("Loader", (yaml.SafeLoader,), {})
    loader.add_multi_constructor("!", lambda loader_, suffix, node: None)
    switches = yaml.load(content, Loader=loader)["switch"]
    tech = osmo["technical_name"]
    public = next(sw for sw in switches if sw.get("id") == tech)
    assert public["platform"] == "template"
    relay = next(sw for sw in switches if sw.get("internal") and sw["platform"] == "gpio"
                 and {"switch.template.publish": {"id": tech, "state": "ON"}} in sw.get("on_turn_on", []))
    assert relay["on_turn_on"][0] == {"switch.template.publish": {"id": tech, "state": "ON"}}
    assert relay["on_turn_off"][0] == {"switch.template.publish": {"id": tech, "state": "OFF"}}


def test_rule_group_light_names_are_per_aquarium(api, aquarium, controller, uid):
    api.patch(f"/controllers/{controller['id']}", {"rtc_model": "DS3231"})
    other = api.post("/aquariums/", {"name": f"Bac nom {uid}", "volume": 100, "water_type": "sea",
                                     "biotope": "récifal", "date_creation": "2026-01-01"}, code=201)
    pump_a = api.post("/equipments/", equipment_payload(aquarium, controller, "12", f"Pompe A {uid}"), code=201)
    pump_b = api.post("/equipments/", equipment_payload(other, controller, "13", f"Pompe B {uid}"), code=201)
    pump_a2 = api.post("/equipments/", equipment_payload(aquarium, controller, "14", f"Pompe A2 {uid}"), code=201)

    # Règles : même nom dans deux aquariums, refus clair (400, plus de 500) dans le même
    rule = {**_time_rule(pump_a["id"], uid), "name": "Pause repas"}
    api.post("/rules/", rule, code=201)
    api.post("/rules/", {**rule, "equipment_id": pump_b["id"]}, code=201)
    assert "Pause repas" in api.post("/rules/", {**rule, "equipment_id": pump_a2["id"]}, code=400)["detail"]

    # Groupes : l'aquarium vient des équipements du groupe
    api.post("/equipment-groups/", {"name": "Brassage", "equipment_ids": [pump_a["id"]]}, code=200)
    api.post("/equipment-groups/", {"name": "Brassage", "equipment_ids": [pump_b["id"]]}, code=200)
    api.post("/equipment-groups/", {"name": "brassage", "equipment_ids": [pump_a2["id"]]}, code=400)

    # Lampes : unique par aquarium
    light = {"name": "Rampe", "aquarium_id": aquarium["id"], "controller_id": controller["id"]}
    api.post("/lights/", light, code=201)
    api.post("/lights/", {**light, "aquarium_id": other["id"]}, code=201)
    api.post("/lights/", light, code=400)


def test_rule_states_follow_sensor_inversion(api, aquarium, controller, uid):
    """Règle exprimée comme l'affichage (HIGH = eau haute) ; le firmware lit la broche brute."""
    from sqlalchemy import text

    import main
    from models.sensor import Sensor
    from services.esphome_generator import _find_off_guards

    osmo = api.post("/equipments/", equipment_payload(aquarium, controller, "12", f"Osmolateur {uid}"), code=201)
    level = {"aquarium_id": aquarium["id"], "controller_id": controller["id"], "type": "binary_sensor", "unit": "level"}
    inverted = api.post("/sensors/", {**level, "name": f"Niveau inv {uid}", "pin_id": controller["pins"]["13"], "is_inverted": True}, code=201)
    normal = api.post("/sensors/", {**level, "name": f"Niveau {uid}", "pin_id": controller["pins"]["14"]}, code=201)
    for sensor in (inverted, normal):
        api.post("/rules/", {"name": f"Plein {sensor['id']}", "action": "OFF", "equipment_id": osmo["id"],
                             "conditions": [{"sensor_id": sensor["id"], "condition_type": "SENSOR_STATE", "trigger_state": "HIGH"}]},
                 code=201)
    db = SessionLocal()
    try:
        ctrl = db.get(Controller, controller["id"])
        eq = next(e for e in ctrl.equipments if e.id == osmo["id"])
        guards = dict(_find_off_guards(eq, ctrl))
        # Eau haute : broche HIGH pour le capteur normal, LOW (!state) pour le capteur inversé
        assert guards[normal["technical_name"]] == f"id({normal['technical_name']}).state"
        assert guards[inverted["technical_name"]] == f"!id({inverted['technical_name']}).state"

        # Migration : les règles saisies en état brut sur un capteur inversé sont converties une seule fois
        db.execute(text("UPDATE rule_conditions SET trigger_state = 'LOW' WHERE sensor_id = :s"), {"s": inverted["id"]})
        db.execute(text("DELETE FROM schema_migrations WHERE name = 'rule_states_logical'"))
        db.commit()
        main._apply_data_migrations()
        main._apply_data_migrations()  # deuxième passage : sans effet
        state = db.execute(text("SELECT trigger_state FROM rule_conditions WHERE sensor_id = :s"), {"s": inverted["id"]}).scalar()
        assert state == "HIGH"
        assert db.execute(text("SELECT trigger_state FROM rule_conditions WHERE sensor_id = :s"), {"s": normal["id"]}).scalar() == "HIGH"
        assert db.get(Sensor, inverted["id"]).is_inverted is True
    finally:
        db.close()


def test_toggling_inversion_keeps_physical_behaviour(api, aquarium, controller, uid):
    """Changer l'inversion d'un flotteur ne doit pas changer ce que fait la règle (risque de débordement)."""
    from services.esphome_generator import _find_off_guards

    osmo = api.post("/equipments/", equipment_payload(aquarium, controller, "15", f"Osmo bis {uid}"), code=201)
    sensor = api.post("/sensors/", {"aquarium_id": aquarium["id"], "controller_id": controller["id"], "type": "binary_sensor",
                                    "unit": "level", "name": f"Flotteur {uid}", "pin_id": controller["pins"]["18"]}, code=201)
    rule = api.post("/rules/", {"name": f"Plein bis {uid}", "action": "OFF", "equipment_id": osmo["id"],
                                "conditions": [{"sensor_id": sensor["id"], "condition_type": "SENSOR_STATE", "trigger_state": "HIGH"}]},
                    code=201)

    def guard():
        db = SessionLocal()
        try:
            ctrl = db.get(Controller, controller["id"])
            eq = next(e for e in ctrl.equipments if e.id == osmo["id"])
            return dict(_find_off_guards(eq, ctrl))[sensor["technical_name"]]
        finally:
            db.close()

    before = guard()
    api.patch(f"/sensors/{sensor['id']}", {"is_inverted": True})
    assert next(r for r in api.get("/rules/") if r["id"] == rule["id"])["conditions"][0]["trigger_state"] == "LOW"
    assert guard() == before  # même broche, même état : comportement physique inchangé
    api.patch(f"/sensors/{sensor['id']}", {"is_inverted": True})  # sans changement : rien ne bascule
    assert next(r for r in api.get("/rules/") if r["id"] == rule["id"])["conditions"][0]["trigger_state"] == "LOW"


def test_single_rule_osmolator_on_low_with_revert_and_max_duration(api, aquarium, controller, uid):
    """Une seule règle : allumer quand c'est bas, éteindre dès que ce n'est plus le cas, 20 s au plus."""
    osmo = api.post("/equipments/", equipment_payload(aquarium, controller, "19", f"Osmolateur solo {uid}"), code=201)
    sensor = api.post("/sensors/", {"aquarium_id": aquarium["id"], "controller_id": controller["id"], "type": "binary_sensor",
                                    "unit": "level", "name": f"Flotteur solo {uid}", "pin_id": controller["pins"]["21"]}, code=201)
    rule = api.post("/rules/", {"name": f"Appoint {uid}", "action": "ON", "equipment_id": osmo["id"], "revert_on_exit": True,
                                "max_duration_seconds": 20,
                                "conditions": [{"sensor_id": sensor["id"], "condition_type": "SENSOR_STATE", "trigger_state": "LOW"}]},
                    code=201)
    db = SessionLocal()
    try:
        content = generate_esphome_yaml(db.get(Controller, controller["id"]))
    finally:
        db.close()
    loader = type("Loader", (yaml.SafeLoader,), {})
    loader.add_multi_constructor("!", lambda loader_, suffix, node: None)
    config = yaml.load(content, Loader=loader)
    scripts = {s["id"]: s for s in config["script"]}
    rid = rule["id"]
    # Action : allumer puis couper au bout de 20 s ; action inverse : couper dès que le niveau remonte
    assert f"rule_{rid}_action" in scripts and f"rule_{rid}_revert" in scripts
    assert '"delay": "20s"' in str(scripts[f"rule_{rid}_action"]).replace("'", '"')
    assert f"rule_{rid}_eval" in content
    assert "leave" in content  # arrêt (et annulation du délai) à la sortie de la condition
    # Évaluée aussi au démarrage du contrôleur
    assert {"script.execute": f"rule_{rid}_eval"} in config["esphome"]["on_boot"]["then"]


def test_osmolator_default_safety_is_45s(api, aquarium, controller, uid):
    api.post("/equipments/", equipment_payload(aquarium, controller, "22", f"Osmolateur 45 {uid}"), code=201)
    custom = api.post("/equipments/", equipment_payload(aquarium, controller, "23", f"Osmolateur 60 {uid}",
                                                        max_duration_seconds=60), code=201)
    db = SessionLocal()
    try:
        content = generate_esphome_yaml(db.get(Controller, controller["id"]))
    finally:
        db.close()
    assert "Timeout de securite 45s" in content  # durée non renseignée
    assert "Timeout de securite 60s" in content and custom["max_duration_seconds"] == 60


def test_same_name_in_two_aquariums_on_one_controller(api, aquarium, controller, uid):
    """Deux « Osmolateur » (un par aquarium) sur un contrôleur : ESPHome exige des noms distincts."""
    other = api.post("/aquariums/", {"name": f"Frag {uid}", "volume": 100, "water_type": "sea",
                                     "biotope": "récifal", "date_creation": "2026-01-01"}, code=201)
    first = api.post("/equipments/", equipment_payload(aquarium, controller, "12", "Osmolateur"), code=201)
    second = api.post("/equipments/", equipment_payload(other, controller, "13", "Osmolateur"), code=201)
    level = {"controller_id": controller["id"], "type": "binary_sensor", "unit": "level", "name": "Niveau décante"}
    s1 = api.post("/sensors/", {**level, "aquarium_id": aquarium["id"], "pin_id": controller["pins"]["14"]}, code=201)
    s2 = api.post("/sensors/", {**level, "aquarium_id": other["id"], "pin_id": controller["pins"]["15"]}, code=201)
    db = SessionLocal()
    try:
        content = generate_esphome_yaml(db.get(Controller, controller["id"]))
    finally:
        db.close()
    loader = type("Loader", (yaml.SafeLoader,), {})
    loader.add_multi_constructor("!", lambda loader_, suffix, node: None)
    switches = {sw["id"]: sw.get("name") for sw in yaml.load(content, Loader=loader)["switch"]}
    assert switches[first["technical_name"]] == f"Osmolateur ({aquarium['name']})"
    assert switches[second["technical_name"]] == f"Osmolateur (Frag {uid})"
    # Topic MQTT = nom technique, quel que soit le nom affiché (sinon capteur « en attente »)
    prefix = f"/{controller['technical_name']}/binary_sensor/"
    binaries = {b["id"]: b for b in yaml.load(content, Loader=loader)["binary_sensor"]}
    for sensor in (s1, s2):
        conf = binaries[sensor["technical_name"]]
        assert conf["state_topic"].endswith(prefix + sensor["technical_name"] + "/state")
    assert binaries[s1["technical_name"]]["name"] != binaries[s2["technical_name"]]["name"]


def test_osmolator_revert_after_pause_needs_a_low_level(api, aquarium, controller, uid):
    """Fin d'une pause horaire « puis le rallumer » : un osmolateur ne repart que si un
    niveau demande de l'eau (sinon il tournait à vide jusqu'au timeout de sécurité)."""
    api.patch(f"/controllers/{controller['id']}", {"rtc_model": "DS3231"})
    level = api.post("/equipments/", equipment_payload(aquarium, controller, "25", f"Osmolateur niveau {uid}"), code=201)
    blind = api.post("/equipments/", equipment_payload(aquarium, controller, "26", f"Osmolateur seul {uid}"), code=201)
    pump = api.post("/equipments/", equipment_payload(aquarium, controller, "27", f"Brassage pause {uid}"), code=201)
    sensor = api.post("/sensors/", {"aquarium_id": aquarium["id"], "controller_id": controller["id"], "type": "binary_sensor",
                                    "unit": "level", "name": f"Flotteur pause {uid}", "pin_id": controller["pins"]["32"]}, code=201)
    api.post("/rules/", {"name": f"Appoint {uid}", "action": "ON", "equipment_id": level["id"],
                         "conditions": [{"sensor_id": sensor["id"], "condition_type": "SENSOR_STATE", "trigger_state": "LOW"}]},
             code=201)
    rules = {eq["id"]: api.post("/rules/", _time_rule(eq["id"], f"{uid}-{eq['id']}"), code=201) for eq in (level, blind, pump)}
    db = SessionLocal()
    try:
        content = generate_esphome_yaml(db.get(Controller, controller["id"]))
    finally:
        db.close()
    loader = type("Loader", (yaml.SafeLoader,), {})
    loader.add_multi_constructor("!", lambda loader_, suffix, node: None)
    scripts = {s["id"]: str(s) for s in yaml.load(content, Loader=loader)["script"]}
    level_revert = scripts[f"rule_{rules[level['id']]['id']}_revert"]
    blind_revert = scripts[f"rule_{rules[blind['id']]['id']}_revert"]
    pump_revert = scripts[f"rule_{rules[pump['id']]['id']}_revert"]
    assert "safe_turn_on_" in level_revert and "Niveau OK, rallumage ignore" in level_revert
    assert "Niveau OK, rallumage ignore" in blind_revert
    # Condition de dosage (lambda, non relu par le loader) : le flotteur pour l'un, rien pour l'autre
    level_block = content.split(f"id: rule_{rules[level['id']]['id']}_revert")[1].split("\n- id:")[0]
    blind_block = content.split(f"id: rule_{rules[blind['id']]['id']}_revert")[1].split("\n- id:")[0]
    assert "flotteur_pause" in level_block
    assert "return false;" in blind_block
    # Équipement ordinaire : rallumage inchangé
    assert "Niveau OK" not in pump_revert


def test_float_pins_input_only_gpio_and_extension_module(api, aquarium, controller, uid):
    """GPIO 34-39 : pas de tirage interne ; broche de module : lue via le PCF8574."""
    cid = controller["id"]
    api.post("/sensors/", {"aquarium_id": aquarium["id"], "controller_id": cid, "type": "binary_sensor",
                           "unit": "level", "name": f"Niveau 34 {uid}", "pin_id": controller["pins"]["34"]}, code=201)
    api.post(f"/controllers/{cid}/modules", {"address": "0x24", "type": "PCF8574"})
    module_pin = next(p for p in api.get(f"/controllers/{cid}/pins")["controller_pins"]
                      if p["module_number"] and p["pin_number"] == "0")
    api.post("/sensors/", {"aquarium_id": aquarium["id"], "controller_id": cid, "type": "binary_sensor",
                           "unit": "level", "name": f"Niveau module {uid}", "pin_id": module_pin["id"]}, code=201)
    db = SessionLocal()
    try:
        content = generate_esphome_yaml(db.get(Controller, cid))
    finally:
        db.close()
    loader = type("Loader", (yaml.SafeLoader,), {})
    loader.add_multi_constructor("!", lambda loader_, suffix, node: None)
    sensors = {s["id"]: s for s in yaml.load(content, Loader=loader)["binary_sensor"]}
    gpio34 = next(s for k, s in sensors.items() if k.startswith(f"niveau_34_{uid}"))
    on_module = next(s for k, s in sensors.items() if k.startswith(f"niveau_module_{uid}"))
    assert gpio34["pin"] == {"number": 34, "mode": "INPUT"}
    assert on_module["pin"] == {"pcf8574": "pcf8574_0x24", "number": 0, "mode": {"input": True}}


def test_shared_one_wire_pin_requires_addresses(api, aquarium, controller, uid):
    """Deux sondes sur une broche : adresse obligatoire ; une sonde sans adresse n'emprunte
    jamais la mesure d'une autre (capteur vide dans le firmware)."""
    cid = controller["id"]
    probe = {"aquarium_id": aquarium["id"], "controller_id": cid, "type": "sensor", "unit": "temperature",
             "pin_id": controller["pins"]["4"]}
    first = api.post("/sensors/", {**probe, "name": f"Temp A {uid}", "address": "0x2801234567890abc"}, code=201)
    api.post("/sensors/", {**probe, "name": f"Temp B {uid}"}, code=409)
    api.post("/sensors/", {**probe, "name": f"Temp B {uid}", "address": "0x2801234567890abc"}, code=409)
    second = api.post("/sensors/", {**probe, "name": f"Temp B {uid}", "address": "0x28ffffffffffff01"}, code=201)
    assert first["address"] != second["address"]

    # Données anciennes : une sonde sans adresse sur un bus partagé
    from models.sensor import Sensor
    db = SessionLocal()
    try:
        db.get(Sensor, second["id"]).address = None
        db.commit()
        content = generate_esphome_yaml(db.get(Controller, cid))
    finally:
        db.close()
    loader = type("Loader", (yaml.SafeLoader,), {})
    loader.add_multi_constructor("!", lambda loader_, suffix, node: None)
    sensors = {s["id"]: s for s in yaml.load(content, Loader=loader)["sensor"]}
    a = next(s for k, s in sensors.items() if k.startswith(f"temp_a_{uid}"))
    b = next(s for k, s in sensors.items() if k.startswith(f"temp_b_{uid}"))
    assert a["platform"] == "dallas_temp" and a["address"] == "0x2801234567890abc"
    assert b["platform"] == "template" and "index" not in b


def test_osmolator_fault_clear_resets_counter_and_resumes(api, aquarium, controller, uid):
    """« Réinitialiser » : compteur de cycles remis à zéro et dosage relancé si le niveau le demande."""
    osmo = api.post("/equipments/", equipment_payload(aquarium, controller, "19", f"Osmolateur reprise {uid}"), code=201)
    sensor = api.post("/sensors/", {"aquarium_id": aquarium["id"], "controller_id": controller["id"], "type": "binary_sensor",
                                    "unit": "level", "name": f"Flotteur reprise {uid}", "pin_id": controller["pins"]["21"]}, code=201)
    api.post("/rules/", {"name": f"Appoint reprise {uid}", "action": "ON", "equipment_id": osmo["id"],
                         "conditions": [{"sensor_id": sensor["id"], "condition_type": "SENSOR_STATE", "trigger_state": "LOW"}]},
             code=201)
    db = SessionLocal()
    try:
        content = generate_esphome_yaml(db.get(Controller, controller["id"]))
    finally:
        db.close()
    loader = type("Loader", (yaml.SafeLoader,), {})
    loader.add_multi_constructor("!", lambda loader_, suffix, node: None)
    config = yaml.load(content, Loader=loader)
    name = osmo["technical_name"]
    clear = next(m for m in config["mqtt"]["on_message"] if m["topic"].endswith(f"/switch/{name}/fault/clear"))
    block = content.split(f"/switch/{name}/fault/clear")[1].split("\n  - topic:")[0]
    assert f"id(activation_count_{name}) = 0;" in block and f"id(fault_latched_{name}) = false;" in block
    assert f"safe_turn_on_{name}" in str(clear["then"]) and "reprise apres acquittement" in str(clear["then"])
    assert "flotteur_reprise" in block  # condition de niveau évaluée avant la reprise


def test_moonlight_on_several_channels(api, aquarium, controller, uid):
    """Clair de lune sur plusieurs canaux (ex. canal du driver + canal bleu), chacun à son intensité."""
    from middleware.database import SessionLocal
    from models.light import Light
    from services.light_control import settings_payload
    from models.controller import Controller
    from services.esphome_generator import generate_esphome_yaml

    api.patch(f"/controllers/{controller['id']}", {"rtc_model": "DS3231"})
    light = api.post("/lights/", {"name": f"Rampe lune {uid}", "aquarium_id": aquarium["id"],
                                  "controller_id": controller["id"]}, code=201)
    for name, pin, spectrum in (("Driver", "25", "white"), ("Bleu", "26", "blue"), ("Blanc", "27", "white")):
        light = api.post(f"/lights/{light['id']}/channels", {"name": name, "pin_id": controller["pins"][pin],
                                                             "spectrum": spectrum}, code=201)
    ids = {c["name"]: c["id"] for c in light["channels"]}

    light = api.patch(f"/lights/{light['id']}", {"moonlight": [{"channel_id": ids["Driver"], "intensity": 30},
                                                               {"channel_id": ids["Bleu"], "intensity": 5}]})
    assert sorted((m["channel_id"], m["intensity"]) for m in light["moonlight"]) == sorted(
        [(ids["Driver"], 30), (ids["Bleu"], 5)])
    assert {c["name"]: c["moonlight_intensity"] for c in light["channels"]} == {"Driver": 30, "Bleu": 5, "Blanc": 0}

    with SessionLocal() as db:
        row = db.get(Light, light["id"])
        moon = settings_payload(row)["moon"]
        firmware = generate_esphome_yaml(db.get(Controller, controller["id"]))
    assert moon["channels"] == {str(ids["Driver"]): 30, str(ids["Bleu"]): 5}
    assert moon["channel"] == ids["Driver"] and moon["value"] == 30  # firmware plus ancien : premier canal
    lid = f"light{light['id']}"
    for name, value in (("Driver", 30), ("Bleu", 5), ("Blanc", 0)):
        assert f"{lid}_moon{ids[name]}" in firmware
    assert f"if (v < id({lid}_moon{ids['Bleu']})) v = id({lid}_moon{ids['Bleu']});" in firmware

    # Liste vide : plus de clair de lune ; canal étranger refusé
    light = api.patch(f"/lights/{light['id']}", {"moonlight": []})
    assert light["moonlight"] == []
    api.patch(f"/lights/{light['id']}", {"moonlight": [{"channel_id": 999999, "intensity": 5}]}, code=400)


def test_profile_start_time_shifts_the_whole_program(api, aquarium, controller, uid):
    """Profil appliqué avec une heure de début : toutes les courbes décalées, minuit compris."""
    api.patch(f"/controllers/{controller['id']}", {"rtc_model": "DS3231"})
    reef = next(p for p in api.get("/lights/catalog")["profiles"] if p["key"] == "reef")
    assert (reef["start"], reef["end"]) == (9 * 60, 21 * 60 + 30)

    light = api.post("/lights/", {"name": f"Rampe profil {uid}", "aquarium_id": aquarium["id"],
                                  "controller_id": controller["id"]}, code=201)
    for name, pin, spectrum in (("Bleu royal", "25", "royal_blue"), ("Blanc", "26", "white")):
        light = api.post(f"/lights/{light['id']}/channels", {"name": name, "pin_id": controller["pins"][pin],
                                                             "spectrum": spectrum}, code=201)

    def schedules(data):
        return {c["name"]: [(p["minute"], p["intensity"]) for p in c["schedule"]] for c in data["channels"]}

    default = schedules(api.post(f"/lights/{light['id']}/apply-profile", {"profile": "reef"}))
    assert default["Bleu royal"][0] == (540, 0)

    # Début à 11 h : décalage de 2 h pour tous les canaux, écarts conservés
    later = schedules(api.post(f"/lights/{light['id']}/apply-profile", {"profile": "reef", "start": 11 * 60}))
    for name in default:
        assert later[name] == [(m + 120, v) for m, v in default[name]]

    # Début à 20 h : la fin passe après minuit, points repliés sur 24 h et triés
    night = schedules(api.post(f"/lights/{light['id']}/apply-profile", {"profile": "reef", "start": 20 * 60}))
    assert night["Bleu royal"] == [(360, 85), (510, 0), (1200, 0), (1320, 85)]
    api.post(f"/lights/{light['id']}/apply-profile", {"profile": "reef", "start": 1440}, code=422)


def test_channel_min_threshold_reaches_firmware_without_reflash(api, aquarium, controller, uid):
    """Seuil d'allumage : réglable en direct (MQTT), appliqué par le firmware, jamais au-dessus du plafond."""
    from models.light import Light
    from services.light_control import settings_payload

    api.patch(f"/controllers/{controller['id']}", {"rtc_model": "DS3231"})
    light = api.post("/lights/", {"name": f"Rampe seuil {uid}", "aquarium_id": aquarium["id"],
                                  "controller_id": controller["id"]}, code=201)
    light = api.post(f"/lights/{light['id']}/channels", {"name": "Blanc", "pin_id": controller["pins"]["25"],
                                                         "spectrum": "white", "max_intensity": 80}, code=201)
    channel = light["channels"][0]
    assert channel["min_intensity"] == 0

    with SessionLocal() as db:
        db.query(Controller).filter(Controller.id == controller["id"]).update({Controller.is_dirty: False})
        db.commit()
    light = api.patch(f"/lights/channels/{channel['id']}", {"min_intensity": 8})
    assert light["channels"][0]["min_intensity"] == 8
    with SessionLocal() as db:
        assert db.get(Controller, controller["id"]).is_dirty is False  # pas de reflash pour le seuil
    api.patch(f"/lights/channels/{channel['id']}", {"min_intensity": 90}, code=400)
    api.patch(f"/lights/channels/{channel['id']}", {"max_intensity": 5}, code=400)

    with SessionLocal() as db:
        row = db.get(Light, light["id"])
        assert settings_payload(row)["channels"][str(channel["id"])]["min"] == 8
        firmware = generate_esphome_yaml(db.get(Controller, controller["id"]))
    lid, cid = f"light{light['id']}", channel["id"]
    assert f"if (v < id({lid}_min{cid})) v = 0.0f;" in firmware
    assert f'id({lid}_min{cid}) = c["min"] | id({lid}_min{cid});' in firmware
    assert "interval: 500ms" in firmware
