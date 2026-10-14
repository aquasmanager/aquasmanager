"""
Génération ESPHome des lampes.

Par canal : une sortie PWM ledc et des globales mémorisées en flash (courbe
de 24 points maximum, mode, intensité manuelle, plafond, seuil d'allumage). Par lampe : une
boucle (deux fois par seconde) qui calcule l'intensité de chaque canal (interpolation
linéaire entre les points, avec passage de minuit), applique clair de lune,
acclimatation et plafond, puis publie l'état. Les réglages arrivent par MQTT
(voir services/light_control.py) : l'ESP suit son programme même sans serveur.
"""

from services.esphome_lambda import ESPLambda
from services.light_control import MAX_SCHEDULE_POINTS, channel_points, settings_payload

_MODE_CODES = {"AUTO": 0, "MANUAL": 1, "OFF": 2}
_ARRAY_TYPE = f"std::array<int16_t, {MAX_SCHEDULE_POINTS * 2}>"

_INTERPOLATE = """auto interp = [](const %s &p, float m) -> float {
  int n = 0;
  while (n < %d && p[2 * n] >= 0) n++;
  if (n == 0) return 0.0f;
  if (n == 1) return p[1];
  for (int i = 0; i < n; i++) {
    int j = (i + 1) %% n;
    float m0 = p[2 * i], m1 = p[2 * j], v0 = p[2 * i + 1], v1 = p[2 * j + 1], mm = m;
    if (j == 0) { m1 += 1440; if (mm < m0) mm += 1440; }
    if (mm >= m0 && mm <= m1) return m1 == m0 ? v1 : v0 + (v1 - v0) * (mm - m0) / (m1 - m0);
  }
  return p[1];
};
""" % (_ARRAY_TYPE, MAX_SCHEDULE_POINTS)


def _points_initializer(points: list[tuple[int, int]]) -> str:
    flat = [v for point in points for v in point]
    flat += [-1, 0] * (MAX_SCHEDULE_POINTS - len(points))
    return "{" + ", ".join(str(v) for v in flat) + "}"


def _global(gid: str, gtype: str, initial: str, restore: bool = True) -> dict:
    return {"id": gid, "type": gtype, "restore_value": restore, "initial_value": initial}


def build_light_firmware(controller, mqtt_conf) -> dict:
    """Fragments de configuration à fusionner (output, globals, interval, mqtt on_json_message, time)."""
    lights = [light for light in (getattr(controller, "lights", None) or []) if light.light_channels]
    fragments = {"output": [], "globals": [], "interval": [], "on_json_message": []}
    if not lights:
        return fragments

    for light in lights:
        lid = f"light{light.id}"
        base_topic = f"{mqtt_conf.topic_prefix}/{controller.technical_name}/light/{light.id}"
        settings = settings_payload(light)
        channels = light.light_channels

        for ch in channels:
            c = f"{lid}_{{}}{ch.id}"
            module = ch.pin.io_module
            if module is not None:
                # Canal d'un module PCA9685 (fréquence réglée sur le module)
                fragments["output"].append({
                    "platform": "pca9685",
                    "id": c.format("out"),
                    "pca9685_id": f"pca9685_{str(module.address).strip().lower()}",
                    "channel": int(ch.pin.pin_number),
                    "inverted": bool(ch.inverted),
                })
            else:
                fragments["output"].append({
                    "platform": "ledc",
                    "id": c.format("out"),
                    "pin": int(ch.pin.pin_number),
                    "frequency": f"{light.pwm_frequency}Hz",
                    "inverted": bool(ch.inverted),
                })
            fragments["globals"] += [
                _global(c.format("pts"), _ARRAY_TYPE, _points_initializer(channel_points(ch))),
                _global(c.format("mode"), "int", str(_MODE_CODES[ch.mode.value])),
                _global(c.format("manual"), "float", f"{float(ch.current_intensity)}"),
                _global(c.format("max"), "float", f"{float(ch.max_intensity)}"),
                _global(c.format("min"), "float", f"{float(ch.min_intensity)}"),
                _global(c.format("level"), "float", "0.0", restore=False),
                _global(c.format("moon"), "float", f"{float(ch.moonlight_intensity)}"),
            ]

        accl = settings["accl"]
        fragments["globals"] += [
            _global(f"{lid}_accl_start", "uint32_t", str(accl["start"])),
            _global(f"{lid}_accl_days", "int", str(accl["days"])),
            _global(f"{lid}_accl_pct", "float", f"{float(accl['percent'])}"),
            _global(f"{lid}_demo_start", "uint32_t", "0", restore=False),
            _global(f"{lid}_demo_ms", "uint32_t", "0", restore=False),
            _global(f"{lid}_tick", "int", "0", restore=False),
        ]

        # --- Boucle de calcul (1 s) ---
        per_channel = []
        for ch in channels:
            c = f"{lid}_{{}}{ch.id}"
            per_channel.append(f"""{{
  float v;
  int mode = id({c.format('mode')});
  if (demo) v = interp(id({c.format('pts')}), minute);
  else if (mode == 2) v = 0.0f;
  else if (mode == 1) v = id({c.format('manual')});
  else if (minute < 0) v = id({c.format('level')});
  else {{
    v = interp(id({c.format('pts')}), minute) * accl;
    if (v < id({c.format('moon')})) v = id({c.format('moon')});
  }}
  v = std::max(0.0f, std::min(v, id({c.format('max')})));
  // Sous le seuil d'allumage : éteint (zone instable du driver, scintillement)
  if (v < id({c.format('min')})) v = 0.0f;
  id({c.format('level')}) = v;
  id({c.format('out')}).set_level(v / 100.0f);
}}""")
        state_fields = "\n".join(
            f'  root["{ch.id}"] = (int) roundf(id({lid}_level{ch.id}));' for ch in channels
        )
        loop = f"""auto now = id(sntp_time).now();
uint32_t ms = millis();
bool demo = id({lid}_demo_ms) > 0 && (ms - id({lid}_demo_start)) < id({lid}_demo_ms);
if (!demo && id({lid}_demo_ms) > 0) id({lid}_demo_ms) = 0;
float minute = -1.0f;
if (demo) minute = (float) (ms - id({lid}_demo_start)) * 1440.0f / (float) id({lid}_demo_ms);
else if (now.is_valid()) minute = now.hour * 60 + now.minute + now.second / 60.0f;
float accl = 1.0f;
if (now.is_valid() && id({lid}_accl_days) > 0 && id({lid}_accl_start) > 0) {{
  float days = (float) ((int64_t) now.timestamp - (int64_t) id({lid}_accl_start)) / 86400.0f;
  if (days < id({lid}_accl_days)) {{
    float progress = days < 0 ? 0.0f : days / id({lid}_accl_days);
    accl = (id({lid}_accl_pct) + (100.0f - id({lid}_accl_pct)) * progress) / 100.0f;
  }}
}}
{_INTERPOLATE}
{chr(10).join(per_channel)}
id({lid}_tick) += 1;
// État publié toutes les 10 s (chaque seconde en démonstration) ; calcul toutes les 500 ms
if (id({lid}_tick) >= (demo ? 2 : 20)) {{
  id({lid}_tick) = 0;
  id(mqtt_client).publish_json("{base_topic}/state", [=](JsonObject root) {{
{state_fields}
  root["demo"] = demo;
  root["minute"] = (int) minute;
  }});
}}"""
        fragments["interval"].append({"interval": "500ms", "then": [{"lambda": ESPLambda(loop)}]})

        # --- Réception des réglages ---
        schedule_code = "\n".join(
            f"""{{
  JsonArrayConst a = x["channels"]["{ch.id}"];
  if (!a.isNull()) {{
    {_ARRAY_TYPE} t;
    t.fill(-1);
    size_t i = 0;
    for (JsonVariantConst point : a) {{
      if (i >= {MAX_SCHEDULE_POINTS}) break;
      t[2 * i] = point[0] | -1;
      t[2 * i + 1] = point[1] | 0;
      i++;
    }}
    id({lid}_pts{ch.id}) = t;
  }}
}}"""
            for ch in channels
        )
        moon_code = "\n".join(
            f'  id({lid}_moon{ch.id}) = m.isNull() ? (old_ch == {ch.id} ? old_val : 0.0f) : (m["{ch.id}"] | 0.0f);'
            for ch in channels
        )
        settings_code = "\n".join(
            f"""{{
  JsonVariantConst c = x["channels"]["{ch.id}"];
  if (!c.isNull()) {{
    const char *m = c["mode"] | "AUTO";
    id({lid}_mode{ch.id}) = strcmp(m, "MANUAL") == 0 ? 1 : (strcmp(m, "OFF") == 0 ? 2 : 0);
    id({lid}_manual{ch.id}) = c["value"] | id({lid}_manual{ch.id});
    id({lid}_max{ch.id}) = c["max"] | id({lid}_max{ch.id});
    id({lid}_min{ch.id}) = c["min"] | id({lid}_min{ch.id});
  }}
}}"""
            for ch in channels
        ) + f"""
if (!x["moon"].isNull()) {{
  JsonVariantConst m = x["moon"]["channels"];
  int old_ch = x["moon"]["channel"] | 0;
  float old_val = x["moon"]["value"] | 0.0f;
{moon_code}
}}
if (!x["accl"].isNull()) {{
  id({lid}_accl_start) = x["accl"]["start"] | 0u;
  id({lid}_accl_days) = x["accl"]["days"] | 0;
  id({lid}_accl_pct) = x["accl"]["percent"] | 50.0f;
}}"""
        demo_code = f"""if (x["stop"] | false) {{
  id({lid}_demo_ms) = 0;
}} else {{
  uint32_t duration = x["duration_s"] | 60u;
  id({lid}_demo_start) = millis();
  id({lid}_demo_ms) = duration * 1000u;
}}"""
        fragments["on_json_message"] += [
            {"topic": f"{base_topic}/schedule", "qos": 1, "then": [{"lambda": ESPLambda(schedule_code)}]},
            {"topic": f"{base_topic}/set", "qos": 1, "then": [{"lambda": ESPLambda(settings_code)}]},
            {"topic": f"{base_topic}/demo", "then": [{"lambda": ESPLambda(demo_code)}]},
        ]

    return fragments


def apply_light_firmware(config: dict, controller, mqtt_conf) -> bool:
    """Ajoute les lampes à la configuration ; renvoie True si une horloge est nécessaire."""
    fragments = build_light_firmware(controller, mqtt_conf)
    if not fragments["output"]:
        return False
    config.setdefault("output", []).extend(fragments["output"])
    config.setdefault("globals", []).extend(fragments["globals"])
    config.setdefault("interval", []).extend(fragments["interval"])
    config["mqtt"]["id"] = "mqtt_client"
    config["mqtt"].setdefault("on_json_message", []).extend(fragments["on_json_message"])
    return True
