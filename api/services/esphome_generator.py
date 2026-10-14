"""
Génère la configuration ESPHome (YAML) d'un contrôleur : Wi-Fi, MQTT,
horloge, bus I2C et 1-Wire, relais, capteurs, lampes, règles exécutées sur
l'ESP32 (y compris sans serveur) et sécurités des osmolateurs.
"""

import math
import re
import unicodedata
from collections import Counter

import yaml
from models.controller import Controller
from models.sensor import is_temperature_sensor
from services.rule import is_advanced_rule
from services.esphome_lambda import ESPLambda
from services.light_firmware import apply_light_firmware
from settings import settings


# Anti-cyclage des osmolateurs : au-dela de ce nombre d'activations reelles
# (transitions OFF->ON) dans la fenetre glissante, on verrouille (fault latche,
# necessite un acquittement manuel) plutot que de continuer a essayer.
SAFETY_MAX_ACTIVATIONS_PER_WINDOW = 4
SAFETY_ACTIVATION_WINDOW_MS = 15 * 60 * 1000  # 15 minutes


def _rule_target_equipments(rule, controller):
    targets = []
    if getattr(rule, "equipment", None):
        targets.append(rule.equipment)
    elif getattr(rule, "group", None) and getattr(rule, "group", None).equipments:
        targets.extend(rule.group.equipments)
    elif getattr(rule, "group_id", None):
        target_group = next((g for g in getattr(controller, "groups", []) if g.id == rule.group_id), None)
        if target_group and getattr(target_group, "equipments", None):
            targets.extend(target_group.equipments)
    return targets


# Coupure de sécurité d'un osmolateur quand sa durée max n'est pas renseignée
OSMOLATOR_DEFAULT_MAX_SECONDS = 45

OPPOSITE_STATE = {"LOW": "HIGH", "HIGH": "LOW", "OFF": "ON", "ON": "OFF",
                   "FALSE": "TRUE", "TRUE": "FALSE", "CLOSED": "OPEN", "OPEN": "CLOSED"}


def _raw_state(sensor, trigger_state) -> str:
    """
    Les règles sont exprimées comme l'affichage (« niveau haut » = eau haute),
    inversion du capteur comprise ; le firmware lit, lui, la broche brute :
    pour un capteur inversé, on convertit l'état attendu.
    """
    ts = str(trigger_state or "HIGH").upper()
    if getattr(sensor, "is_inverted", False):
        return OPPOSITE_STATE.get(ts, ts)
    return ts


def _condition_active_expr(sensor_id: str, trigger_state: str) -> str:
    ts = str(trigger_state or "HIGH").upper()
    if ts in ("LOW", "OFF", "FALSE", "CLOSED"):
        return f'!id({sensor_id}).state'
    return f'id({sensor_id}).state'


def _match_expr_for_on_state(trigger_state: str) -> str:
    ts = str(trigger_state or "HIGH").upper()
    if ts in ("LOW", "OFF", "FALSE", "CLOSED"):
        return '!x'
    return 'x'


def _entity_key(name: str) -> str:
    # Comparaison proche de l'object_id d'ESPHome : casse, accents et ponctuation ignorés
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", plain).strip("_")


def _unique_entity_names(items) -> dict[str, str]:
    """Nom affiché de chaque entité, unique sur le contrôleur.

    Le même nom est permis dans deux aquariums, mais ESPHome refuse deux entités
    de même nom sur un appareil : on précise alors l'aquarium (« Osmolateur (Récif) »).
    Les topics MQTT reposent sur technical_name, ce nom n'est qu'un libellé.
    """
    counts = Counter(_entity_key(i.name) for i in items)
    names: dict[str, str] = {}
    used: set[str] = set()
    for item in items:
        name = item.name
        aquarium = getattr(getattr(item, "aquarium", None), "name", None)
        if counts[_entity_key(name)] > 1 and aquarium:
            name = f"{name} ({aquarium})"
        base, n = name, 2
        while _entity_key(name) in used:
            name, n = f"{base} {n}", n + 1
        used.add(_entity_key(name))
        names[item.technical_name] = name
    return names


def _is_eq_osmolator(eq) -> bool:
    category = str(getattr(eq, "category", "") or getattr(eq, "type", "")).lower()
    tech_name = str(getattr(eq, "technical_name", "")).lower()
    name = str(getattr(eq, "name", "")).lower()
    return (
        category in ("osmolateur", "osmolator", "topoff") or
        "osmol" in tech_name or
        "osmol" in name
    )


def pca9685_frequency(controller, module) -> int:
    """Fréquence PWM d'un PCA9685 : la plus haute des lampes branchées dessus (1000 Hz sinon),
    bornée à ce que le circuit accepte."""
    frequencies = [
        int(light.pwm_frequency)
        for light in (getattr(controller, "lights", None) or [])
        for ch in (light.light_channels or [])
        if ch.pin is not None and ch.pin.module_id == module.id and light.pwm_frequency
    ]
    return max(24, min(1525, max(frequencies) if frequencies else 1000))


def pca9685_used(controller, module) -> bool:
    """Un PCA9685 sans canal de lampe branché ne doit pas être déclaré : ESPHome ne
    compile alors pas le composant « output » dont il dépend (échec à la compilation)."""
    return any(
        ch.pin is not None and ch.pin.module_id == module.id
        for light in (getattr(controller, "lights", None) or [])
        for ch in (light.light_channels or [])
    )


def restart_topic(topic_prefix: str, controller_name: str) -> str:
    return f"{topic_prefix}/{controller_name}/button/restart/command"


def _i2c_bus(controller) -> dict:
    """Bus I2C (SDA 21, SCL 22) ; fréquence réglable : plus basse pour un câble long."""
    khz = int(getattr(controller, "i2c_frequency_khz", None) or 50)
    return {"sda": 21, "scl": 22, "scan": True, "frequency": f"{khz}kHz"}


# GPIO 34 à 39 de l'ESP32 : entrées seules, sans résistance de tirage interne
INPUT_ONLY_GPIOS = range(34, 40)


def _input_pin_config(pin) -> dict:
    """Broche d'entrée d'un capteur tout-ou-rien (flotteur) :
    - broche d'un module d'extension : via le PCF8574 (et non la GPIO de même numéro) ;
    - GPIO 34 à 39 : entrée simple, une résistance de tirage externe est nécessaire ;
    - autres GPIO : tirage interne vers le 3,3 V."""
    number = int(pin.pin_number)
    module = getattr(pin, "io_module", None)
    if module is not None:
        return {"pcf8574": f"pcf8574_{str(module.address).strip().lower()}", "number": number, "mode": {"input": True}}
    if number in INPUT_ONLY_GPIOS:
        return {"number": number, "mode": "INPUT"}
    return {"number": number, "mode": "INPUT_PULLUP"}


def _get_turn_on_action(eq_name: str, is_osmolator: bool, has_lock: bool = False, source: str = "commande") -> dict:
    if is_osmolator:
        # Origine écrite dans le log « Demarrage (...) » : diagnostic d'un démarrage inattendu
        return {"script.execute": {"id": f"safe_turn_on_{eq_name}", "source": source}}
    if has_lock:
        return {"script.execute": f"guarded_turn_on_{eq_name}"}
    return {"switch.turn_on": eq_name}


def _get_turn_off_action(eq_name: str, is_osmolator: bool, has_lock: bool = False) -> dict:
    if is_osmolator:
        return {"script.execute": f"safe_turn_off_{eq_name}"}
    if has_lock:
        return {"script.execute": f"guarded_turn_off_{eq_name}"}
    return {"switch.turn_off": eq_name}


def _find_off_guards(eq, controller):
    """Règles qui ETEIGNENT eq (action == OFF) : sert de garde-fou avant
    une restauration ON au boot."""
    guards = []
    eq_name = getattr(eq, "technical_name", None)
    for s in getattr(controller, "sensors", None) or []:
        for condition in getattr(s, "rule_conditions", None) or []:
            rule = getattr(condition, "rule", None)
            if not rule or not getattr(rule, "is_active", True) or is_advanced_rule(rule):
                continue
            if str(getattr(rule, "action", "")).upper() != "OFF":
                continue
            targets = _rule_target_equipments(rule, controller)
            target_names = [getattr(t, "technical_name", None) for t in targets]
            if eq_name not in target_names:
                continue
            trigger_state = _raw_state(s, getattr(condition, "trigger_state", "LOW"))
            guards.append((s.technical_name, _condition_active_expr(s.technical_name, trigger_state)))
    return guards


def _find_on_triggers(eq, controller):
    """Règles qui ALLUMENT eq (action == ON) : sert à détecter, après un
    arrêt par timeout de sécurité, si la condition de dosage est toujours
    active (anomalie : le dosage n'a pas suffi à faire remonter le niveau)."""
    triggers = []
    eq_name = getattr(eq, "technical_name", None)
    for s in getattr(controller, "sensors", None) or []:
        for condition in getattr(s, "rule_conditions", None) or []:
            rule = getattr(condition, "rule", None)
            if not rule or not getattr(rule, "is_active", True) or is_advanced_rule(rule):
                continue
            if str(getattr(rule, "action", "")).upper() != "ON":
                continue
            targets = _rule_target_equipments(rule, controller)
            target_names = [getattr(t, "technical_name", None) for t in targets]
            if eq_name not in target_names:
                continue
            trigger_state = _raw_state(s, getattr(condition, "trigger_state", "LOW"))
            triggers.append((s.technical_name, _condition_active_expr(s.technical_name, trigger_state)))
    return triggers


def _advanced_on_rule_ids(eq, controller) -> list:
    """Règles avancées actives qui ALLUMENT eq (reprise du dosage après acquittement)."""
    ids = set()
    eq_name = getattr(eq, "technical_name", None)
    candidates = []
    for s in getattr(controller, "sensors", None) or []:
        candidates += [getattr(c, "rule", None) for c in getattr(s, "rule_conditions", None) or []]
    for e in getattr(controller, "equipments", None) or []:
        candidates += list(getattr(e, "rules", None) or [])
        for group in getattr(e, "groups", None) or []:
            candidates += list(getattr(group, "rules", None) or [])
    for rule in candidates:
        if not rule or not getattr(rule, "is_active", True) or not is_advanced_rule(rule):
            continue
        if str(getattr(rule, "action", "")).upper() != "ON":
            continue
        if eq_name in [getattr(t, "technical_name", None) for t in _rule_target_equipments(rule, controller)]:
            ids.add(rule.id)
    return sorted(ids)


def _find_safety_lock_conditions(eq, controller):
    """Règles OFF marquées is_safety_lock=True ciblant eq : interlock de
    sécurité matériel/capteur. S'applique quel que soit le mode AUTO/MANUAL
    de l'équipement (contrairement aux règles normales), et bloque toute
    tentative de rallumage tant que la condition est active."""
    conditions = []
    eq_name = getattr(eq, "technical_name", None)
    for s in getattr(controller, "sensors", None) or []:
        for condition in getattr(s, "rule_conditions", None) or []:
            rule = getattr(condition, "rule", None)
            if not rule or not getattr(rule, "is_active", True) or is_advanced_rule(rule):
                continue
            if not getattr(rule, "is_safety_lock", False):
                continue
            if str(getattr(rule, "action", "")).upper() != "OFF":
                continue
            targets = _rule_target_equipments(rule, controller)
            target_names = [getattr(t, "technical_name", None) for t in targets]
            if eq_name not in target_names:
                continue
            trigger_state = _raw_state(s, getattr(condition, "trigger_state", "LOW"))
            conditions.append((s.technical_name, _condition_active_expr(s.technical_name, trigger_state)))
    return conditions


def _time_range_expr(condition) -> str:
    start = condition.start_time.hour * 60 + condition.start_time.minute
    end = condition.end_time.hour * 60 + condition.end_time.minute
    if start < end:
        return f"(minute_of_day >= {start} && minute_of_day < {end})"
    # Plage qui passe minuit (ex : 22:00 -> 07:00)
    return f"(minute_of_day >= 0 && (minute_of_day >= {start} || minute_of_day < {end}))"


def _advanced_condition_expr(sensor, condition) -> str:
    if condition.condition_type == "TIME_RANGE":
        return _time_range_expr(condition)
    sensor_id = sensor.technical_name
    if condition.condition_type == "THRESHOLD":
        return f"(!std::isnan(id({sensor_id}).state) && id({sensor_id}).state {condition.operator} {float(condition.threshold_value)!r})"
    return f"(id({sensor_id}).has_state() && {_condition_active_expr(sensor_id, _raw_state(sensor, condition.trigger_state))})"


def _build_advanced_rules(controller, mqtt_conf, get_lock_conditions):
    """
    Moteur des règles "avancées" (seuils numériques, plusieurs conditions
    ET/OU). Chaque règle devient deux scripts : rule_<id>_eval recalcule la
    condition combinée à chaque nouvelle valeur d'un de ses capteurs et ne
    déclenche rule_<id>_action qu'au passage faux -> vrai (front montant),
    pour ne pas répéter l'action à chaque mesure.
    Retourne (globals, scripts, {technical_name capteur: [scripts d'évaluation]},
    [scripts à réévaluer chaque minute (plages horaires)]).
    """
    sensors_by_id = {s.id: s for s in (getattr(controller, "sensors", None) or [])}
    candidates = []
    for sensor in sensors_by_id.values():
        candidates += [getattr(c, "rule", None) for c in getattr(sensor, "rule_conditions", None) or []]
    # Une règle purement horaire n'a pas de capteur : on la retrouve par l'équipement piloté
    for eq in getattr(controller, "equipments", None) or []:
        candidates += list(getattr(eq, "rules", None) or [])
        for group in getattr(eq, "groups", None) or []:
            candidates += list(getattr(group, "rules", None) or [])
    rules = {
        rule.id: rule for rule in candidates
        if rule and getattr(rule, "is_active", True) and is_advanced_rule(rule)
    }

    rule_globals, rule_scripts, triggers, minute_evals = [], [], {}, []
    pending_reverts, active_rules = [], []
    for rule in sorted(rules.values(), key=lambda r: r.id):
        conditions = list(rule.conditions)
        sensor_conditions = [c for c in conditions if c.condition_type != "TIME_RANGE"]
        has_time = len(sensor_conditions) < len(conditions)
        if any(c.sensor_id not in sensors_by_id for c in sensor_conditions):
            continue  # capteur sur un autre contrôleur : refusé par l'API, ignoré ici par sécurité
        if has_time and not getattr(controller, "rtc_model", None):
            continue  # plage horaire sans horloge fiable : refusé par l'API, ignoré ici par sécurité

        joiner = " || " if str(rule.match_type).upper() == "OR" else " && "
        expression = joiner.join(_advanced_condition_expr(sensors_by_id.get(c.sensor_id), c) for c in conditions)
        action = str(rule.action).upper()

        def equipment_steps(eq_action: str, rule=rule, osm_demand: dict | None = None) -> list:
            result = []
            for eq in _rule_target_equipments(rule, controller):
                eq_name = getattr(eq, "technical_name", None)
                if not eq_name or getattr(eq, "controller_id", controller.id) != controller.id:
                    continue
                is_osm = _is_eq_osmolator(eq)
                has_lock = bool(get_lock_conditions(eq))
                if eq_action == "ON":
                    source = "fin de regle" if osm_demand is not None else f"regle {rule.id}"
                    eq_steps = [_get_turn_on_action(eq_name, is_osm, has_lock, source)]
                    if rule.max_duration_seconds:
                        eq_steps += [{"delay": f"{rule.max_duration_seconds}s"}, _get_turn_off_action(eq_name, is_osm, has_lock)]
                    if is_osm and osm_demand is not None:
                        # Rallumage d'un osmolateur à la sortie d'une règle (ex : fin
                        # d'une pause horaire) : uniquement si un niveau demande de
                        # l'eau. Sinon, rien ne l'arrêterait avant le timeout de
                        # sécurité (pas de changement de niveau à attendre).
                        eq_steps = [{"if": {
                            "condition": {"lambda": ESPLambda(f"return {osm_demand(eq)};")},
                            "then": eq_steps,
                            "else": [{"logger.log": {
                                "level": "INFO", "tag": eq_name,
                                "format": "Niveau OK, rallumage ignore",
                            }}],
                        }}]
                else:
                    eq_steps = [_get_turn_off_action(eq_name, is_osm, has_lock)]
                if rule.is_safety_lock:
                    # Règle de sécurité : s'applique aussi en mode manuel
                    result.extend(eq_steps)
                else:
                    result.append({"if": {
                        "condition": {"lambda": ESPLambda(
                            f'return id(mode_{eq_name}) == "AUTO" || id(mode_{eq_name}) == "auto";'
                        )},
                        "then": eq_steps,
                    }})
            return result

        steps = []
        if action == "NOTIFY":
            message = (rule.notification_message or f"Règle {rule.name} déclenchée").replace("\n", " ")
            steps.append({"mqtt.publish": {
                "topic": f"{mqtt_conf.topic_prefix}/{controller.technical_name}/notify",
                "payload": message,
                "retain": False,
            }})
        elif action in ("ON", "OFF"):
            steps = equipment_steps(action)
        if not steps:
            continue

        active_id, action_id, eval_id = f"rule_{rule.id}_active", f"rule_{rule.id}_action", f"rule_{rule.id}_eval"
        revert_id = f"rule_{rule.id}_revert"
        has_revert = bool(getattr(rule, "revert_on_exit", False) and action in ("ON", "OFF"))
        rule_globals.append({"id": active_id, "type": "bool", "restore_value": False, "initial_value": "false"})
        rule_scripts.append({"id": action_id, "mode": "restart", "then": steps})
        active_rules.append(rule)
        if has_revert:
            # Script construit après la boucle : le rallumage d'un osmolateur
            # dépend des autres règles (globals rule_<id>_active générés)
            pending_reverts.append((revert_id, rule, "OFF" if action == "ON" else "ON", equipment_steps))
        code = ""
        if has_time:
            code += (
                "auto clock = id(sntp_time).now();\n"
                "int minute_of_day = clock.is_valid() ? clock.hour * 60 + clock.minute : -1;\n"
            )
        code += (
            f"bool now = {expression};\n"
            f"bool fire = now && !id({active_id});\n"
        )
        if has_revert:
            code += f"bool leave = !now && id({active_id});\n"
        code += f"id({active_id}) = now;\nif (fire) id({action_id}).execute();"
        if has_revert:
            code += f"\nif (leave) {{ id({action_id}).stop(); id({revert_id}).execute(); }}"
        rule_scripts.append({"id": eval_id, "then": [{"lambda": ESPLambda(code)}]})
        for condition in sensor_conditions:
            technical_name = sensors_by_id[condition.sensor_id].technical_name
            if eval_id not in triggers.setdefault(technical_name, []):
                triggers[technical_name].append(eval_id)
        if has_time:
            minute_evals.append(eval_id)

    def osm_demand(eq) -> str:
        """Un niveau demande-t-il de l'eau pour cet osmolateur ? (règles simples
        ON sur capteur, ou règle avancée ON avec capteur actuellement vraie)"""
        exprs = [expr for _, expr in _find_on_triggers(eq, controller)]
        for other in active_rules:
            if str(other.action).upper() != "ON":
                continue
            if all(c.condition_type == "TIME_RANGE" for c in other.conditions):
                continue
            if eq.technical_name in [getattr(t, "technical_name", None) for t in _rule_target_equipments(other, controller)]:
                exprs.append(f"id(rule_{other.id}_active)")
        return " || ".join(exprs) if exprs else "false"

    for revert_id, rule, revert_action, build in pending_reverts:
        rule_scripts.append({"id": revert_id, "mode": "restart", "then": build(revert_action, rule, osm_demand)})

    return rule_globals, rule_scripts, triggers, minute_evals


# Modules RTC sur pile -> plateforme ESPHome (le DS3231 est compatible DS1307)
RTC_PLATFORMS = {"DS3231": "ds1307", "DS1307": "ds1307", "PCF8563": "pcf8563", "PCF85063": "pcf85063"}
TIMEZONE = "Europe/Paris"


def _apply_time_sources(config: dict, controller, needs_clock: bool, minute_actions: list | None = None) -> None:
    """
    Heure système : NTP, et si un module RTC sur pile est présent, lu au
    démarrage (heure juste immédiatement, même sans réseau) puis recalé à
    chaque synchronisation NTP. Les autres composants lisent id(sntp_time).
    """
    rtc_platform = RTC_PLATFORMS.get(getattr(controller, "rtc_model", None) or "")
    if not needs_clock and not rtc_platform and not minute_actions:
        return
    sntp = {"platform": "sntp", "id": "sntp_time", "timezone": TIMEZONE}
    if minute_actions:
        # Réévaluation des règles horaires à chaque changement de minute
        sntp["on_time"] = [{"seconds": 0, "then": minute_actions}]
    time_sources = []
    if rtc_platform:
        config.setdefault("i2c", _i2c_bus(controller))
        time_sources.append({"platform": rtc_platform, "id": "rtc_time", "update_interval": "never", "timezone": TIMEZONE})
        sntp["on_time_sync"] = {"then": [{f"{rtc_platform}.write_time": {"id": "rtc_time"}}]}
        read_at_boot = {"priority": 600, "then": [{f"{rtc_platform}.read_time": {"id": "rtc_time"}}]}
        on_boot = config["esphome"].get("on_boot")
        config["esphome"]["on_boot"] = [read_at_boot] + ([on_boot] if isinstance(on_boot, dict) else on_boot or [])
    time_sources.append(sntp)
    config["time"] = time_sources


def generate_esphome_yaml(controller: Controller) -> str:
    mqtt_conf = settings.mqtt
    esp_conf = settings.esp
    network_conf = settings.network

    global_vars = []
    mqtt_on_message_actions = []
    osmolator_clears = []
    scripts = []
    boot_restore_actions = []
    locked_equipment_names = []

    # Cache des conditions d'interlock par équipement (évite de rescanner
    # toutes les règles du contrôleur à chaque référence à un équipement).
    lock_cache = {}

    def get_lock_conditions(eq):
        name = getattr(eq, "technical_name", None)
        if name not in lock_cache:
            lock_cache[name] = _find_safety_lock_conditions(eq, controller)
        return lock_cache[name]

    config = {
        "esphome": {
            "name": controller.technical_name,
            "friendly_name": controller.name
        },
        "esp32": {
            "board": "esp32dev",
            "framework": {
                "type": "arduino"
            }
        },
        "wifi": {
            "ssid": esp_conf.ssid,
            "password": esp_conf.password,
            "manual_ip": {
                "static_ip": controller.ip,
                "gateway": network_conf.gateway,
                "subnet": network_conf.subnet,
                "dns1": getattr(network_conf, "dns1", network_conf.gateway)
            }
        },
        "mqtt": {
            "broker": mqtt_conf.device_host or mqtt_conf.host,
            "username": mqtt_conf.user,
            "password": mqtt_conf.password,
            "topic_prefix": f"{mqtt_conf.topic_prefix}/{controller.technical_name}",
            "discovery": False,
            "birth_message": {
                "topic": f"{mqtt_conf.topic_prefix}/{controller.technical_name}/status",
                "payload": "ONLINE",
                "qos": 1,
                "retain": True
            },
            "will_message": {
                "topic": f"{mqtt_conf.topic_prefix}/{controller.technical_name}/status",
                "payload": "OFFLINE",
                "qos": 1,
                "retain": True
            },
            # Sinon ESPHome publie « offline » (minuscules) à l'arrêt propre
            "shutdown_message": {
                "topic": f"{mqtt_conf.topic_prefix}/{controller.technical_name}/status",
                "payload": "OFFLINE",
                "qos": 1,
                "retain": True
            },
            "log_topic": {
                "topic": f"{mqtt_conf.topic_prefix}/{controller.technical_name}/logs",
                "level": "INFO",
                "qos": 1
            }
        },
        "logger": {},
        "api": {
            "reboot_timeout": "0s"
        },
        "ota": [{"platform": "esphome"}],
    }

    # --- I2C & PCF8574 ---
    io_modules = getattr(controller, "io_modules", None) or getattr(controller, "modules", None)
    if io_modules:
        config["i2c"] = _i2c_bus(controller)
        for mod in io_modules:
            addr_str = str(mod.address).strip()
            addr = int(addr_str, 16) if addr_str.lower().startswith("0x") else int(addr_str)
            module_type = str(getattr(mod.type, "value", mod.type))
            if module_type == "PCA9685":
                if not pca9685_used(controller, mod):
                    continue
                # Sorties PWM (canaux de lampe) : une fréquence pour tout le module,
                # celle des lampes qui l'utilisent (24 à 1525 Hz pour ce circuit)
                config.setdefault("pca9685", []).append({
                    "id": f"pca9685_{addr_str.lower()}",
                    "address": addr,
                    "frequency": f"{pca9685_frequency(controller, mod)}Hz",
                })
            else:
                expander = {"id": f"pcf8574_{addr_str.lower()}", "address": addr}
                if module_type == "PCF8575":
                    expander["pcf8575"] = True  # 16 broches au lieu de 8
                config.setdefault("pcf8574", []).append(expander)

    # --- Pré-calcul du debounce de chaque capteur ---
    # Défaut relevé à 1000ms (au lieu de 300ms) : les flotteurs optiques
    # réagissent à de vraies transitions physiques (micro-vagues, gouttes
    # résiduelles) qui ne sont pas du bruit électrique - un debounce trop
    # court les laisse passer comme des cycles de dosage distincts.
    sensor_debounce_ms = {}
    for s in getattr(controller, "sensors", None) or []:
        unit = getattr(s, "unit", "")
        stype = getattr(s, "type", "")
        if unit in ("niveau", "level") or stype in ("niveau", "level"):
            sensor_debounce_ms[s.technical_name] = int(getattr(s, "debounce_ms", 1000) or 1000)

    def _build_pin_config(pin, inverted_flag):
        """Construit le bloc pin: (avec ou sans PCF8574) pour un switch GPIO."""
        io_mod = getattr(pin, "io_module", None) or getattr(pin, "io_modules", None)
        if isinstance(io_mod, list) and io_mod:
            io_mod = io_mod[0]

        if io_mod:
            mod_addr_str = str(io_mod.address).strip().lower()
            return {
                "pcf8574": f"pcf8574_{mod_addr_str}",
                "number": int(pin.pin_number),
                "mode": "OUTPUT",
                "inverted": inverted_flag
            }
        return {
            "number": int(pin.pin_number),
            "inverted": inverted_flag
        }

    # --- ÉQUIPEMENTS (RELAIS / SWITCHES) ---
    switches = []
    pin_equipments = []
    for pin in getattr(controller, "pins", None) or []:
        eqs = getattr(pin, "equipment", None) or getattr(pin, "equipments", None)
        pin_equipments.extend(e for e in (eqs if isinstance(eqs, list) else [eqs]) if e)
    eq_names = _unique_entity_names(pin_equipments)
    if getattr(controller, "pins", None):
        for pin in controller.pins:
            eqs = getattr(pin, "equipment", None) or getattr(pin, "equipments", None)
            if not eqs:
                continue
            if not isinstance(eqs, list):
                eqs = [eqs]

            for eq in eqs:
                if not eq:
                    continue

                global_id = f"mode_{eq.technical_name}"
                mode_val = eq.mode.value if hasattr(eq.mode, "value") else str(eq.mode)
                is_osm = _is_eq_osmolator(eq)

                lock_conditions = get_lock_conditions(eq)
                has_lock = bool(lock_conditions)
                blocked_id = f"blocked_{eq.technical_name}"
                if has_lock:
                    locked_equipment_names.append(eq.technical_name)
                    global_vars.append({
                        "id": blocked_id,
                        "type": "bool",
                        "restore_value": False,
                        "initial_value": "false"
                    })

                # Un équipement protégé (osmolateur et/ou cible d'un
                # interlock capteur) n'est jamais piloté directement en
                # GPIO/MQTT : seul un relais physique interne existe, la
                # seule interface publique est un switch template dont les
                # actions passent par des scripts qui vérifient les
                # garde-fous avant de faire quoi que ce soit.
                is_protected = is_osm or has_lock

                global_vars.append({
                    "id": global_id,
                    "type": "std::string",
                    "restore_value": True,
                    "initial_value": f'"{mode_val.upper()}"'
                })

                cmd_topic = f"{mqtt_conf.topic_prefix}/{controller.technical_name}/switch/{eq.technical_name}/command"
                state_topic = f"{mqtt_conf.topic_prefix}/{controller.technical_name}/switch/{eq.technical_name}/state"
                fault_topic = f"{mqtt_conf.topic_prefix}/{controller.technical_name}/switch/{eq.technical_name}/fault"
                fault_clear_topic = f"{mqtt_conf.topic_prefix}/{controller.technical_name}/switch/{eq.technical_name}/fault/clear"
                inverted_flag = getattr(eq, "inverted", True)

                # Pour un équipement protégé, la commande physique
                # (switch.turn_on/off, id().state) ne cible JAMAIS l'id
                # public (eq.technical_name), mais un switch GPIO interne
                # dédié. Sans cette séparation, un message MQTT retenu
                # rejoué sur le command_topic public (ex: après une
                # coupure/reconnexion, ou une découverte Home Assistant)
                # déclenche switch.turn_on/off directement, sans passer par
                # les scripts sécurisés — c'est exactement ce qui a causé le
                # déversement de la réserve : aucun timeout, aucune
                # vérification de niveau, aucun anti-cycle.
                relay_id = f"{eq.technical_name}_relay" if is_protected else eq.technical_name

                # --- Scripts de sécurité pour les osmolateurs ---
                if is_osm:
                    max_dur = int(getattr(eq, "max_duration_seconds", None) or OSMOLATOR_DEFAULT_MAX_SECONDS)
                    min_on_s = int(getattr(eq, "min_on_duration_seconds", 10) or 10)
                    min_on_ms = min_on_s * 1000
                    timeout_flag_id = f"timeout_triggered_{eq.technical_name}"
                    fault_latched_id = f"fault_latched_{eq.technical_name}"
                    activation_count_id = f"activation_count_{eq.technical_name}"
                    window_start_id = f"window_start_{eq.technical_name}"

                    global_vars.append({
                        "id": f"last_on_time_{eq.technical_name}",
                        "type": "uint32_t",
                        "restore_value": False,
                        "initial_value": "0"
                    })
                    global_vars.append({
                        "id": timeout_flag_id,
                        "type": "bool",
                        "restore_value": False,
                        "initial_value": "false"
                    })
                    global_vars.append({
                        # Verrou d'anomalie : persiste à travers un reboot
                        # (restore_value: true) volontairement — une
                        # coupure d'élec ne doit jamais effacer
                        # silencieusement un vrai défaut détecté (trop de
                        # cycles, ou niveau toujours bas après le timeout).
                        # Seul un acquittement manuel (topic fault/clear)
                        # le lève.
                        "id": fault_latched_id,
                        "type": "bool",
                        "restore_value": True,
                        "initial_value": "false"
                    })
                    global_vars.append({
                        "id": activation_count_id,
                        "type": "uint16_t",
                        "restore_value": False,
                        "initial_value": "0"
                    })
                    global_vars.append({
                        "id": window_start_id,
                        "type": "uint32_t",
                        "restore_value": False,
                        "initial_value": "0"
                    })

                    on_trigger_pairs = _find_on_triggers(eq, controller)
                    on_trigger_exprs = [expr for _, expr in on_trigger_pairs]
                    still_needed_expr = " || ".join(on_trigger_exprs) if on_trigger_exprs else "false"

                    gate_parts = [f'!id({fault_latched_id})']
                    if has_lock:
                        gate_parts.append(f'!id({blocked_id})')
                    gate_expr = " && ".join(gate_parts)

                    turn_on_body = [
                        {"switch.turn_on": relay_id},
                        {"lambda": ESPLambda(
                            f'id(last_on_time_{eq.technical_name}) = millis();\n'
                            f'id({timeout_flag_id}) = false;'
                        )},
                        {"logger.log": {
                            "level": "INFO",
                            "tag": eq.technical_name,
                            "format": "Demarrage (%s)",
                            "args": ["source.c_str()"]
                        }},
                        {"mqtt.publish": {
                            "topic": fault_topic,
                            "payload": "OK",
                            "retain": True
                        }},
                        {"delay": f"{max_dur}s"},
                        {"lambda": ESPLambda(f'id({timeout_flag_id}) = true;')},
                        {"logger.log": {
                            "level": "WARN",
                            "tag": eq.technical_name,
                            "format": f"Timeout de securite {max_dur}s atteint, arret force"
                        }},
                        {"script.execute": f"safe_turn_off_{eq.technical_name}"}
                    ]

                    scripts.append({
                        "id": f"safe_turn_on_{eq.technical_name}",
                        "parameters": {"source": "string"},
                        # "single" (et non "restart") : si le script tourne
                        # déjà (la pompe est en train de doser), un nouveau
                        # déclenchement (ex: rebond du capteur de niveau)
                        # est ignoré au lieu de relancer le chrono de
                        # sécurité à zéro. C'est ce bug précis (mode:
                        # restart) qui permettait à un capteur bruyant de
                        # faire tourner la pompe indéfiniment malgré le
                        # timeout.
                        "mode": "single",
                        "then": [
                            {
                                "if": {
                                    "condition": {"lambda": ESPLambda(f'return {gate_expr};')},
                                    "then": [
                                        {"lambda": ESPLambda(
                                            f'uint32_t now_ms = millis();\n'
                                            f'if (now_ms - id({window_start_id}) > {SAFETY_ACTIVATION_WINDOW_MS}) {{\n'
                                            f'  id({window_start_id}) = now_ms;\n'
                                            f'  id({activation_count_id}) = 0;\n'
                                            f'}}\n'
                                            f'id({activation_count_id})++;'
                                        )},
                                        {
                                            "if": {
                                                "condition": {
                                                    "lambda": ESPLambda(
                                                        f'return id({activation_count_id}) > {SAFETY_MAX_ACTIVATIONS_PER_WINDOW};'
                                                    )
                                                },
                                                "then": [
                                                    {"lambda": ESPLambda(f'id({fault_latched_id}) = true;')},
                                                    {"logger.log": {
                                                        "level": "ERROR",
                                                        "tag": eq.technical_name,
                                                        "format": (
                                                            f"Trop de cycles "
                                                            f"({SAFETY_MAX_ACTIVATIONS_PER_WINDOW}+) en "
                                                            f"{SAFETY_ACTIVATION_WINDOW_MS // 60000} min, "
                                                            f"verrouillage de securite"
                                                        )
                                                    }},
                                                    {"mqtt.publish": {
                                                        "topic": fault_topic,
                                                        "payload": "TOO_MANY_CYCLES",
                                                        "retain": True
                                                    }}
                                                ],
                                                "else": turn_on_body
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    })

                    scripts.append({
                        "id": f"safe_turn_off_{eq.technical_name}",
                        "then": [
                            {"script.stop": f"safe_turn_on_{eq.technical_name}"},
                            {
                                "if": {
                                    "condition": {"lambda": ESPLambda(f'return id({relay_id}).state;')},
                                    "then": [
                                        {
                                            "if": {
                                                "condition": {
                                                    "lambda": ESPLambda(
                                                        f'return (millis() - id(last_on_time_{eq.technical_name})) < {min_on_ms};'
                                                    )
                                                },
                                                "then": [
                                                    {"delay": ESPLambda(
                                                        f'return {min_on_ms} - (millis() - id(last_on_time_{eq.technical_name}));'
                                                    )}
                                                ]
                                            }
                                        },
                                        {"switch.turn_off": relay_id},
                                        {"logger.log": {
                                            "level": "INFO",
                                            "tag": eq.technical_name,
                                            "format": "Arret"
                                        }},
                                        {
                                            "if": {
                                                "condition": {
                                                    "lambda": ESPLambda(
                                                        f'return id({timeout_flag_id}) && ({still_needed_expr});'
                                                    )
                                                },
                                                "then": [
                                                    {"lambda": ESPLambda(f'id({fault_latched_id}) = true;')},
                                                    {"logger.log": {
                                                        "level": "ERROR",
                                                        "tag": eq.technical_name,
                                                        "format": "ANOMALIE: condition de dosage toujours active apres le timeout"
                                                    }},
                                                    {"mqtt.publish": {
                                                        "topic": fault_topic,
                                                        "payload": "LEVEL_TIMEOUT",
                                                        "retain": True
                                                    }}
                                                ]
                                            }
                                        },
                                        {"lambda": ESPLambda(f'id({timeout_flag_id}) = false;')}
                                    ]
                                }
                            }
                        ]
                    })

                elif has_lock:
                    # Équipement non-osmolateur mais cible d'un interlock
                    # capteur (ex: écumeur coupé par le niveau haut de la
                    # décante) : pas de logique de dosage, juste la garde.
                    scripts.append({
                        "id": f"guarded_turn_on_{eq.technical_name}",
                        "mode": "single",
                        "then": [
                            {
                                "if": {
                                    "condition": {"lambda": ESPLambda(f'return !id({blocked_id});')},
                                    "then": [{"switch.turn_on": relay_id}]
                                }
                            }
                        ]
                    })
                    scripts.append({
                        "id": f"guarded_turn_off_{eq.technical_name}",
                        "then": [{"switch.turn_off": relay_id}]
                    })

                mode_command_topic = f"{mqtt_conf.topic_prefix}/{controller.technical_name}/switch/{eq.technical_name}/mode/set"
                mode_status_topic = f"{mqtt_conf.topic_prefix}/{controller.technical_name}/switch/{eq.technical_name}/mode"

                # --- Handler mode/set : mémorise le mode UNIQUEMENT ---
                # Ne réévalue plus l'état courant du capteur ici. Avant, ce
                # handler dupliquait la logique du binary_sensor.on_state,
                # mais sans la protection last_state_X - un message reçu
                # deux fois (retained, reconnexion MQTT, republication de
                # l'app) relançait safe_turn_on/off une seconde fois pour
                # rien, produisant des doubles "Demarrage" rapprochés. Le
                # binary_sensor.on_state (protégé par last_state_X) et
                # sensor_boot_actions (au boot) couvrent déjà tous les cas
                # réels de changement de mode + niveau déjà bas/haut.
                on_msg_then = [
                    {"lambda": ESPLambda(f'id({global_id}) = x;')},
                    {
                        "mqtt.publish": {
                            "topic": mode_status_topic,
                            "payload": ESPLambda(f'return id({global_id}).c_str();'),
                            "retain": True
                        }
                    }
                ]

                mqtt_on_message_actions.append({
                    "topic": mode_command_topic,
                    "then": on_msg_then
                })

                # Acquittement manuel d'un verrou d'anomalie : tout osmolateur
                # peut se verrouiller lui-même (TOO_MANY_CYCLES, LEVEL_TIMEOUT)
                # indépendamment d'une éventuelle règle d'interlock capteur
                # (has_lock) — les deux sont des mécanismes distincts. Les
                # interlocks capteurs, eux, se relâchent tout seuls, pas
                # besoin d'acquittement.
                if is_osm:
                    # Construit après les règles avancées : la reprise du dosage
                    # dépend aussi de leurs conditions (rule_<id>_active)
                    osmolator_clears.append((eq, fault_topic, fault_clear_topic, still_needed_expr))

                boot_restore_actions.append({
                    "lambda": ESPLambda(f'if (id({global_id}).empty()) {{ id({global_id}) = "AUTO"; }}')
                })

                boot_restore_actions.append({
                    "mqtt.publish": {
                        "topic": mode_status_topic,
                        "payload": ESPLambda(f'return id({global_id}).c_str();'),
                        "retain": True
                    }
                })

                restore_mode_setting = str(getattr(eq, "restore_mode", "OFF")).upper()
                restore_delay = int(getattr(eq, "restore_delay_seconds", 0) or 0)
                want_on_id = None
                restore_on_turn_on_actions = []
                restore_on_turn_off_actions = []

                if restore_mode_setting == "ON":
                    want_on_id = f"want_on_{eq.technical_name}"
                    global_vars.append({
                        "id": want_on_id,
                        "type": "bool",
                        "restore_value": True,
                        "initial_value": "false"
                    })
                    restore_on_turn_on_actions.append({"lambda": ESPLambda(f'id({want_on_id}) = true;')})
                    restore_on_turn_off_actions.append({"lambda": ESPLambda(f'id({want_on_id}) = false;')})

                    guard_pairs = _find_off_guards(eq, controller)
                    guard_exprs = [expr for _, expr in guard_pairs]

                    if guard_exprs:
                        allow_condition = f'return !({" || ".join(guard_exprs)});'
                        max_guard_debounce_s = max(
                            (sensor_debounce_ms.get(sid, 1000) for sid, _ in guard_pairs),
                            default=0
                        ) / 1000.0
                        effective_delay = max(restore_delay, max_guard_debounce_s + 1)
                    else:
                        allow_condition = 'return true;'
                        effective_delay = restore_delay

                    script_id = f"restore_script_{eq.technical_name}"
                    script_then = []
                    if effective_delay > 0:
                        script_then.append({"delay": f"{math.ceil(effective_delay)}s"})
                    script_then.append({
                        "if": {
                            "condition": {"lambda": ESPLambda(allow_condition)},
                            "then": [_get_turn_on_action(eq.technical_name, is_osm, has_lock, "reprise au demarrage")]
                        }
                    })

                    scripts.append({"id": script_id, "then": script_then})

                    boot_restore_actions.append({
                        "if": {
                            "condition": {"lambda": ESPLambda(f'return id({want_on_id});')},
                            "then": [{"script.execute": script_id}]
                        }
                    })

                if is_protected:
                    # 1) Switch GPIO physique, jamais exposé en MQTT/API :
                    # c'est lui qui pilote réellement le relais.
                    physical_sw = {
                        "platform": "gpio",
                        "id": relay_id,
                        "internal": True,
                        "restore_mode": "ALWAYS_OFF",
                        "pin": _build_pin_config(pin, inverted_flag)
                    }
                    # Le switch public ne relit le relais que toutes les 60 s
                    # (update_interval par défaut d'un template) : un complément
                    # d'osmolateur plus court passait inaperçu (ni état MQTT, ni
                    # activation). On publie donc l'état au moment exact du changement.
                    publish_on = {"switch.template.publish": {"id": eq.technical_name, "state": "ON"}}
                    publish_off = {"switch.template.publish": {"id": eq.technical_name, "state": "OFF"}}
                    physical_sw["on_turn_on"] = [publish_on, *restore_on_turn_on_actions]
                    physical_sw["on_turn_off"] = [publish_off, *restore_on_turn_off_actions]
                    switches.append(physical_sw)

                    # 2) Switch public (template) : seule interface exposée
                    # en MQTT/API. Toute commande dessus est redirigée vers
                    # les scripts sécurisés/gardés, jamais vers le relais
                    # directement.
                    template_sw = {
                        "platform": "template",
                        "name": eq_names[eq.technical_name],
                        "id": eq.technical_name,
                        "state_topic": state_topic,
                        "command_topic": cmd_topic,
                        "lambda": ESPLambda(f'return id({relay_id}).state;'),
                        "turn_on_action": [_get_turn_on_action(eq.technical_name, is_osm, has_lock, "commande MQTT")],
                        "turn_off_action": [_get_turn_off_action(eq.technical_name, is_osm, has_lock)]
                    }
                    switches.append(template_sw)
                else:
                    sw_config = {
                        "platform": "gpio",
                        "name": eq_names[eq.technical_name],
                        "id": eq.technical_name,
                        "restore_mode": "ALWAYS_OFF",
                        "state_topic": state_topic,
                        "command_topic": cmd_topic,
                        "pin": _build_pin_config(pin, inverted_flag)
                    }
                    if restore_on_turn_on_actions:
                        sw_config["on_turn_on"] = restore_on_turn_on_actions
                    if restore_on_turn_off_actions:
                        sw_config["on_turn_off"] = restore_on_turn_off_actions
                    switches.append(sw_config)

    if switches:
        config["switch"] = switches

    if global_vars:
        config["globals"] = global_vars
    if scripts:
        config["script"] = scripts

    # --- CAPTEURS ---
    sensors = []
    binary_sensors = []
    sensor_boot_actions = []

    advanced_globals, advanced_scripts, advanced_triggers, minute_evals = _build_advanced_rules(
        controller, mqtt_conf, get_lock_conditions
    )

    # Acquittement d'un défaut d'osmolateur (« Réinitialiser » dans l'appli) : verrou levé,
    # compteur de cycles remis à zéro (sinon le démarrage suivant reverrouille), et
    # reprise immédiate du dosage si le niveau le demande encore (le flotteur, déjà bas,
    # ne change pas d'état et ne relancerait rien).
    generated_rules = {g["id"] for g in advanced_globals}
    for eq, fault_topic, fault_clear_topic, still_needed_expr in osmolator_clears:
        name = eq.technical_name
        demand = [still_needed_expr] if still_needed_expr != "false" else []
        demand += [
            f"id({active})" for active in sorted(
                f"rule_{rule_id}_active" for rule_id in _advanced_on_rule_ids(eq, controller)
            ) if active in generated_rules
        ]
        then = [
            {"lambda": ESPLambda(
                f'id(fault_latched_{name}) = false;\n'
                f'id(activation_count_{name}) = 0;\n'
                f'id(window_start_{name}) = millis();\n'
                f'id(timeout_triggered_{name}) = false;'
            )},
            {"mqtt.publish": {"topic": fault_topic, "payload": "OK", "retain": True}},
        ]
        if demand:
            then.append({"if": {
                "condition": {"lambda": ESPLambda(
                    f'return (id(mode_{name}) == "AUTO" || id(mode_{name}) == "auto") && ({" || ".join(demand)});'
                )},
                "then": [_get_turn_on_action(name, True, False, "reprise apres acquittement")],
            }})
        mqtt_on_message_actions.append({"topic": fault_clear_topic, "then": then})
    if mqtt_on_message_actions:
        config["mqtt"]["on_message"] = mqtt_on_message_actions
    global_vars.extend(advanced_globals)
    scripts.extend(advanced_scripts)

    def _rule_trigger_actions(sensor) -> list:
        return [{"script.execute": script_id} for script_id in advanced_triggers.get(sensor.technical_name, [])]

    all_sensors = getattr(controller, "sensors", None) or []
    sensor_names = _unique_entity_names(all_sensors)
    one_wire_buses: dict[int, str] = {}
    probes_per_pin: dict[int, int] = {}
    for probe in all_sensors:
        if is_temperature_sensor(probe):
            probe_pin = getattr(probe, "pin", None)
            number = int(probe_pin.pin_number) if probe_pin and getattr(probe_pin, "pin_number", None) else 4
            probes_per_pin[number] = probes_per_pin.get(number, 0) + 1
    if all_sensors:

        for s in all_sensors:
            sensor_unit = getattr(s, "unit", "")
            sensor_type = getattr(s, "type", "")

            if is_temperature_sensor(s):
                pin_obj = getattr(s, "pin", None)
                pin_number = int(pin_obj.pin_number) if pin_obj and getattr(pin_obj, "pin_number", None) else 4
                bus_id = one_wire_buses.setdefault(pin_number, f"one_wire_gpio{pin_number}")

                dallas_conf = {
                    "platform": "dallas_temp",
                    "name": sensor_names[s.technical_name],
                    "id": s.technical_name,
                    "one_wire_id": bus_id,
                    "update_interval": f"{getattr(s, 'interval', None) or 30}s",
                    # object_id ESPHome dérivé du nom ("Température" ->
                    # "temp_rature") ≠ technical_name attendu par drivers/mqtt.py
                    "state_topic": f"{mqtt_conf.topic_prefix}/{controller.technical_name}/sensor/{s.technical_name}/state",
                }
                if getattr(s, "address", None):
                    dallas_conf["address"] = s.address
                elif probes_per_pin.get(pin_number, 0) > 1:
                    # Sans adresse sur un bus partagé, « la 1re sonde trouvée » peut être
                    # celle d'un autre bac : capteur vide (aucune valeur, mêmes identifiants
                    # pour les règles) tant que l'adresse n'est pas renseignée
                    sensors.append({
                        "platform": "template",
                        "name": sensor_names[s.technical_name],
                        "id": s.technical_name,
                        "update_interval": "never",
                        "lambda": ESPLambda("return NAN;"),
                        "state_topic": dallas_conf["state_topic"],
                    })
                    continue
                else:
                    dallas_conf["index"] = 0
                if _rule_trigger_actions(s):
                    dallas_conf["on_value"] = {"then": _rule_trigger_actions(s)}
                sensors.append(dallas_conf)

            elif sensor_unit in ("niveau", "level") or sensor_type in ("niveau", "level"):
                pin_obj = getattr(s, "pin", None)
                if pin_obj and getattr(pin_obj, "pin_number", None):
                    debounce_ms = sensor_debounce_ms.get(s.technical_name, 1000)
                    bin_sensor_config = {
                        "platform": "gpio",
                        "name": sensor_names[s.technical_name],
                        "id": s.technical_name,
                        # Topic fixé : sinon ESPHome le dérive du nom affiché
                        # (« Niveau (Récif) » -> niveau__r_cif_), inconnu de drivers/mqtt.py
                        "state_topic": f"{mqtt_conf.topic_prefix}/{controller.technical_name}/binary_sensor/{s.technical_name}/state",
                        "pin": _input_pin_config(pin_obj),
                        "filters": [
                            {"delayed_on": f"{debounce_ms}ms"},
                            {"delayed_off": f"{debounce_ms}ms"}
                        ]
                    }

                    if hasattr(s, "rule_conditions") and s.rule_conditions:
                        # Trois familles d'actions déclenchées par ce
                        # capteur : les règles normales ON/OFF (existant,
                        # actives seulement en mode AUTO), les interlocks de
                        # sécurité (nouveau, actifs quel que soit le mode,
                        # auto-relâchés) et les notifications pures (nouveau,
                        # aucune action équipement).
                        on_state_actions = []
                        lock_state_actions = []
                        notify_state_actions = []

                        for condition in s.rule_conditions:
                            rule = getattr(condition, "rule", None)
                            if not rule or not getattr(rule, "is_active", True) or is_advanced_rule(rule):
                                continue

                            trigger_state = _raw_state(s, getattr(condition, "trigger_state", "LOW"))
                            action = str(getattr(rule, "action", "OFF")).upper()
                            match_expr = _match_expr_for_on_state(trigger_state)

                            if action == "NOTIFY":
                                message = getattr(rule, "notification_message", None)
                                if not message:
                                    message = f"{s.name}: changement d'etat"
                                message = message.replace("\n", " ")
                                notify_topic = f"{mqtt_conf.topic_prefix}/{controller.technical_name}/notify"
                                notify_state_actions.append({
                                    "mqtt.publish": {
                                        "topic": notify_topic,
                                        "payload": message,
                                        "retain": False
                                    }
                                })
                                continue

                            target_equipments = _rule_target_equipments(rule, controller)
                            if not target_equipments:
                                continue

                            is_lock_rule = bool(getattr(rule, "is_safety_lock", False)) and action == "OFF"

                            for target_eq in target_equipments:
                                eq_name = getattr(target_eq, "technical_name", None)
                                if not eq_name:
                                    continue

                                is_osm_target = _is_eq_osmolator(target_eq)
                                lock_conditions_target = get_lock_conditions(target_eq)
                                has_lock_target = bool(lock_conditions_target)

                                if is_lock_rule:
                                    if not has_lock_target:
                                        continue
                                    blocked_target_id = f"blocked_{eq_name}"
                                    lock_expr = " || ".join(expr for _, expr in lock_conditions_target)
                                    target_relay = f"{eq_name}_relay" if (is_osm_target or has_lock_target) else eq_name
                                    target_fault_topic = f"{mqtt_conf.topic_prefix}/{controller.technical_name}/switch/{eq_name}/fault"
                                    off_action = _get_turn_off_action(eq_name, is_osm_target, has_lock_target)

                                    lock_state_actions.append({
                                        "lambda": ESPLambda(f'id({blocked_target_id}) = ({lock_expr});')
                                    })
                                    lock_state_actions.append({
                                        "if": {
                                            "condition": {
                                                "lambda": ESPLambda(
                                                    f'return id({blocked_target_id}) && id({target_relay}).state;'
                                                )
                                            },
                                            "then": [
                                                off_action,
                                                {"mqtt.publish": {
                                                    "topic": target_fault_topic,
                                                    "payload": "SENSOR_INTERLOCK",
                                                    "retain": True
                                                }}
                                            ]
                                        }
                                    })
                                    lock_state_actions.append({
                                        "if": {
                                            "condition": {
                                                "lambda": ESPLambda(f'return !id({blocked_target_id});')
                                            },
                                            "then": [
                                                {"mqtt.publish": {
                                                    "topic": target_fault_topic,
                                                    "payload": "OK",
                                                    "retain": True
                                                }}
                                            ]
                                        }
                                    })
                                    continue

                                if action not in ("ON", "OFF"):
                                    continue

                                global_id = f"mode_{eq_name}"

                                def rule_steps(source: str) -> list:
                                    if action == "ON":
                                        steps = [_get_turn_on_action(eq_name, is_osm_target, has_lock_target, source)]
                                    else:
                                        steps = [_get_turn_off_action(eq_name, is_osm_target, has_lock_target)]
                                    if action == "ON" and getattr(rule, "max_duration_seconds", None) and rule.max_duration_seconds > 0:
                                        steps.append({"delay": f"{rule.max_duration_seconds}s"})
                                        steps.append(_get_turn_off_action(eq_name, is_osm_target, has_lock_target))
                                    return steps

                                on_state_actions.append({
                                    "if": {
                                        "condition": {
                                            "lambda": ESPLambda(f'return id({global_id}) == "AUTO" || id({global_id}) == "auto";')
                                        },
                                        "then": [
                                            {
                                                "if": {
                                                    "condition": {
                                                        "lambda": ESPLambda(f'return {match_expr};')
                                                    },
                                                    "then": rule_steps(f"{s.technical_name} {trigger_state}")
                                                }
                                            }
                                        ]
                                    }
                                })

                                sensor_boot_actions.append({
                                    "if": {
                                        "condition": {
                                            "lambda": ESPLambda(
                                                f'return id({s.technical_name}).has_state() && '
                                                f'(id({global_id}) == "AUTO" || id({global_id}) == "auto") && '
                                                f'{_condition_active_expr(s.technical_name, trigger_state)};'
                                            )
                                        },
                                        "then": rule_steps(f"{s.technical_name} {trigger_state} au demarrage")
                                    }
                                })

                        all_actions = on_state_actions + lock_state_actions + notify_state_actions
                        if all_actions:
                            last_state_id = f"last_state_{s.technical_name}"
                            global_vars.append({
                                "id": last_state_id,
                                "type": "bool",
                                "restore_value": False,
                                "initial_value": "false"
                            })

                            bin_sensor_config["on_state"] = {
                                "then": [
                                    {
                                        "if": {
                                            "condition": {
                                                "lambda": ESPLambda(f'return x != id({last_state_id});')
                                            },
                                            "then": (
                                                [{"lambda": ESPLambda(f'id({last_state_id}) = x;')}]
                                                + all_actions
                                            )
                                        }
                                    }
                                ]
                            }

                    if _rule_trigger_actions(s):
                        bin_sensor_config.setdefault("on_state", {"then": []})["then"].extend(_rule_trigger_actions(s))
                    binary_sensors.append(bin_sensor_config)

            else:
                pin_obj = getattr(s, "pin", None)
                if pin_obj and getattr(pin_obj, "pin_number", None):
                    sensors.append({
                        "platform": "adc",
                        "name": sensor_names[s.technical_name],
                        "id": s.technical_name,
                        "state_topic": f"{mqtt_conf.topic_prefix}/{controller.technical_name}/sensor/{s.technical_name}/state",
                        "pin": int(pin_obj.pin_number),
                        "update_interval": "60s"
                    })

    # Les capteurs ont pu ajouter des globales/scripts après leur première affectation
    if global_vars:
        config["globals"] = global_vars
    if scripts:
        config["script"] = scripts

    if one_wire_buses:
        config["one_wire"] = [
            {"platform": "gpio", "id": bus_id, "pin": pin_number}
            for pin_number, bus_id in one_wire_buses.items()
        ]

    if sensors:
        config["sensor"] = sensors
    if binary_sensors:
        config["binary_sensor"] = binary_sensors

    # Recalcul initial des verrous d'interlock au boot, AVANT toute
    # tentative de reprise automatique (elle-même placée dans
    # sensor_boot_actions juste après) : sans ça, un équipement pourrait
    # brièvement tenter de redémarrer avant que l'état réel du capteur de
    # sécurité soit pris en compte.
    if locked_equipment_names:
        lock_boot_inits = []
        seen = set()
        for eq_name in locked_equipment_names:
            if eq_name in seen:
                continue
            seen.add(eq_name)
            conditions = lock_cache.get(eq_name) or []
            if not conditions:
                continue
            lock_expr = " || ".join(expr for _, expr in conditions)
            lock_boot_inits.append({"lambda": ESPLambda(f'id(blocked_{eq_name}) = ({lock_expr});')})
        sensor_boot_actions = lock_boot_inits + sensor_boot_actions

    # Règles avancées évaluées aussi au démarrage (comme les règles simples) :
    # un bac déjà bas au démarrage est complété sans attendre un changement d'état
    advanced_boot_evals = []
    for eval_ids in advanced_triggers.values():
        for eval_id in eval_ids:
            if {"script.execute": eval_id} not in advanced_boot_evals:
                advanced_boot_evals.append({"script.execute": eval_id})
    sensor_boot_actions = sensor_boot_actions + advanced_boot_evals

    if sensor_boot_actions:
        boot_restore_actions.append({"delay": "2s"})
        boot_restore_actions.extend(sensor_boot_actions)

    if boot_restore_actions:
        boot_restore_actions.insert(0, {"delay": "500ms"})
        config["esphome"]["on_boot"] = {"priority": 0, "then": boot_restore_actions}

    needs_clock = apply_light_firmware(config, controller, mqtt_conf)
    _apply_time_sources(config, controller, needs_clock, [{"script.execute": sid} for sid in minute_evals])

    # Redémarrage à distance (bouton de l'appli) : nouveau scan I2C et 1-Wire au démarrage
    config["button"] = [{
        "platform": "restart",
        "name": "Redémarrer",
        "id": "restart_button",
        "command_topic": restart_topic(mqtt_conf.topic_prefix, controller.technical_name),
    }]

    return yaml.dump(config, sort_keys=False, default_flow_style=False)
