"""Notes automatiques du journal de bord (ajout d'un vivant, maintenance)."""

import logging
from datetime import date, datetime, time
from typing import Optional

from sqlalchemy.orm import Session

from models.journal import JournalEntry

logger = logging.getLogger(__name__)


def add(db: Session, aquarium_id: int, category: str, text: str,
        occurred_at: Optional[datetime] = None) -> Optional[JournalEntry]:
    """Ajoute une note automatique ; ne fait jamais échouer l'action qui l'écrit."""
    try:
        entry = JournalEntry(aquarium_id=aquarium_id, category=category, text=text[:500], auto=True,
                             occurred_at=occurred_at or datetime.now())
        db.add(entry)
        db.flush()
        return entry
    except Exception:
        logger.exception("Journal : note automatique non enregistrée")
        return None


def livestock_added(db: Session, aquarium_id: int, name: str, quantity: int, acquired: Optional[date]) -> None:
    # Datée de l'acquisition (midi, heure locale arrondie) plutôt que de la saisie
    when = datetime.combine(acquired, time(12)) if acquired and acquired <= date.today() else None
    add(db, aquarium_id, "livestock", f"Ajout : {quantity} × {name}" if quantity > 1 else f"Ajout : {name}", when)
