"""
Purge des défauts d'équipement anciens et résolus.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models.fault import EquipmentFault

logger = logging.getLogger(__name__)


def purge_old_faults(db: Session, retention_days: int) -> int:
    """
    Supprime les défauts équipement résolus depuis plus de retention_days.
    Les défauts encore ouverts (resolved_at NULL) ne sont jamais purgés,
    quel que soit leur âge.
    """
    cutoff = datetime.now() - timedelta(days=retention_days)
    deleted = (
        db.query(EquipmentFault)
        .filter(EquipmentFault.resolved_at.isnot(None), EquipmentFault.resolved_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    if deleted:
        logger.info("Purge des défauts équipement : %d ligne(s) de plus de %dj supprimée(s).", deleted, retention_days)
    return deleted
