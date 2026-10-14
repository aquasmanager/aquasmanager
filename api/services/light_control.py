"""
Pilotage des lampes par MQTT.

Topics (sous le préfixe MQTT, par lampe) :
  <contrôleur>/light/<id>/schedule  (retenu) programme de chaque canal
  <contrôleur>/light/<id>/set       (retenu) mode et intensité manuelle de chaque canal
  <contrôleur>/light/<id>/demo      journée accélérée (non retenu)
  <contrôleur>/light/<id>/state     publié par l'ESP : intensité réelle de chaque canal
Les messages retenus permettent à un ESP hors ligne de récupérer le dernier
réglage à sa reconnexion ; il les mémorise aussi en flash.
"""

import logging
from datetime import date, datetime, time
from typing import Optional

from models.light import Light
from models.light_channel import LightChannel

logger = logging.getLogger(__name__)

MAX_SCHEDULE_POINTS = 24


def channel_points(channel: LightChannel) -> list[tuple[int, int]]:
    points = sorted((s.schedule_time.hour * 60 + s.schedule_time.minute, s.intensity) for s in channel.schedules)
    return points[:MAX_SCHEDULE_POINTS]


def acclimation_percent(light: Light, today: Optional[date] = None) -> Optional[int]:
    """Facteur (%) appliqué au programme ce jour-là, None si pas d'acclimatation en cours."""
    if not light.acclimation_start or not light.acclimation_days:
        return None
    elapsed = ((today or date.today()) - light.acclimation_start).days
    if elapsed >= light.acclimation_days:
        return None
    progress = max(0.0, elapsed / light.acclimation_days)
    start = light.acclimation_start_percent
    return round(start + (100 - start) * progress)


def _topic(light: Light, suffix: str) -> str:
    return f"{light.controller.technical_name}/light/{light.id}/{suffix}"


def _publish(sub_topic: str, payload: dict, retain: bool) -> None:
    from drivers.mqtt import mqtt_driver

    try:
        mqtt_driver.publish(sub_topic, payload, retain=retain, qos=1)
    except Exception as e:
        logger.error(f"Publication MQTT lumière impossible ({sub_topic}) : {e}")


def publish_schedule(light: Light) -> None:
    _publish(
        _topic(light, "schedule"),
        {"channels": {str(ch.id): [list(p) for p in channel_points(ch)] for ch in light.light_channels}},
        retain=True,
    )


def settings_payload(light: Light) -> dict:
    """Réglages modifiables sans reflasher : mode, intensité manuelle, plafond et seuil de
    chaque canal, clair de lune, acclimatation."""
    accl_start = 0
    if light.acclimation_start and light.acclimation_days:
        accl_start = int(datetime.combine(light.acclimation_start, time.min).timestamp())
    return {
        "channels": {
            str(ch.id): {"mode": ch.mode.value, "value": ch.current_intensity, "max": ch.max_intensity,
                         "min": ch.min_intensity}
            for ch in light.light_channels
        },
        # channels : firmware actuel ; channel/value : premier canal, pour un firmware
        # flashé avant le clair de lune sur plusieurs canaux
        "moon": {
            "channels": {str(ch.id): ch.moonlight_intensity for ch in light.light_channels if ch.moonlight_intensity},
            "channel": next((ch.id for ch in light.light_channels if ch.moonlight_intensity), 0),
            "value": next((ch.moonlight_intensity for ch in light.light_channels if ch.moonlight_intensity), 0),
        },
        "accl": {
            "start": accl_start,
            "days": light.acclimation_days or 0,
            "percent": light.acclimation_start_percent,
        },
    }


def publish_channel_states(light: Light) -> None:
    _publish(_topic(light, "set"), settings_payload(light), retain=True)


def publish_demo(light: Light, duration_s: Optional[int]) -> None:
    _publish(_topic(light, "demo"), {"duration_s": duration_s} if duration_s else {"stop": True}, retain=False)
