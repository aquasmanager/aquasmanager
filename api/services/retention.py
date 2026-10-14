"""Purge des relevés de capteurs trop anciens (sensor_reading_retention_days)."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

BATCH_SIZE = 20000


def purge_old_sensor_readings(db: Session, retention_days: int) -> int:
    """Supprime par lots (base peu bloquée) ; 0 jour = conservation illimitée."""
    if retention_days <= 0:
        return 0
    cutoff = datetime.now() - timedelta(days=retention_days)
    total = 0
    while True:
        result = db.execute(
            text(
                "DELETE FROM sensors_reading WHERE id IN "
                "(SELECT id FROM sensors_reading WHERE timestamp < :cutoff LIMIT :batch)"
            ),
            {"cutoff": cutoff, "batch": BATCH_SIZE},
        )
        db.commit()
        total += result.rowcount or 0
        if (result.rowcount or 0) < BATCH_SIZE:
            break
    if total:
        logger.info("Purge des relevés de capteurs : %s lignes de plus de %s jours supprimées", total, retention_days)
    return total
