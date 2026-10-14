"""
Sondes de température muettes.

Une sonde absente dès le démarrage du contrôleur n'envoie rien du tout (pas même
« nan ») : sa dernière valeur resterait affichée. Au-delà de 3 intervalles de
lecture sans mesure, elle est effacée et l'appli affiche « Pas de mesure ».
Les flotteurs ne sont pas concernés : ils ne publient qu'au changement d'état.
"""

import logging
from datetime import datetime, timedelta
from typing import Callable, Optional

from sqlalchemy.orm import Session

from models.sensor import Sensor, is_temperature_sensor

logger = logging.getLogger(__name__)

MISSED_INTERVALS = 3
DEFAULT_INTERVAL_SECONDS = 30


def clear_silent_probes(db: Session, now: Optional[datetime] = None, notify: Optional[Callable[[dict], None]] = None) -> list[int]:
    now = now or datetime.now()
    cleared = []
    for sensor in db.query(Sensor).filter(Sensor.last_value.isnot(None)):
        if not is_temperature_sensor(sensor):
            continue
        limit = timedelta(seconds=MISSED_INTERVALS * (sensor.interval or DEFAULT_INTERVAL_SECONDS))
        if sensor.last_reading_at is not None and now - sensor.last_reading_at <= limit:
            continue
        sensor.last_value = None
        cleared.append(sensor.id)
    if cleared:
        db.commit()
        logger.info("Pas de mesure depuis %d intervalles : %d sonde(s)", MISSED_INTERVALS, len(cleared))
        for sensor_id in cleared:
            if notify:
                notify({"type": "SENSOR_READING", "sensor_id": sensor_id, "value": None})
    return cleared
