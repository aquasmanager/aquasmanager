"""
Échéances des tâches d'entretien : retard, prochaine occurrence, calendrier.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Iterator, Optional
from zoneinfo import ZoneInfo

from models.maintenance_task import MaintenanceTask, TaskRecurrence
from settings import settings


# --- Échéances en heure locale ------------------------------------------------
# Les dates sont stockées naïves en UTC ; une échéance saisie « sans heure »
# est enregistrée à midi. Le jour d'échéance est donc le jour local de cet
# instant. Une tâche est « en retard » à partir du lendemain, à l'heure du
# rappel quotidien (task_reminder_hour) : pas d'alerte au milieu de la nuit.


def local_now() -> datetime:
    return datetime.now(ZoneInfo(settings.timezone))


def due_local_date(due: datetime) -> date:
    return due.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(settings.timezone)).date()


def _reference_date(now: Optional[datetime] = None) -> date:
    return ((now or local_now()) - timedelta(hours=settings.task_reminder_hour)).date()


def is_overdue(due: Optional[datetime], now: Optional[datetime] = None) -> bool:
    return due is not None and due_local_date(due) < _reference_date(now)


def days_overdue(due: Optional[datetime], now: Optional[datetime] = None) -> int:
    return max(0, (_reference_date(now) - due_local_date(due)).days) if due else 0


def is_due_today(due: Optional[datetime], now: Optional[datetime] = None) -> bool:
    return due is not None and due_local_date(due) == (now or local_now()).date()

# Le mois est approximé à 30 jours : suffisant pour un rappel d'entretien,
# évite une dépendance supplémentaire (dateutil) pour un calcul calendaire
# exact que ce cas d'usage ne demande pas.
_RECURRENCE_DAYS = {
    TaskRecurrence.daily: 1,
    TaskRecurrence.weekly: 7,
    TaskRecurrence.monthly: 30,
}


def compute_next_due(
    recurrence: TaskRecurrence, recurrence_days: Optional[int], from_date: datetime
) -> Optional[datetime]:
    if recurrence == TaskRecurrence.none:
        return None
    if recurrence == TaskRecurrence.custom_days:
        return from_date + timedelta(days=recurrence_days or 1)
    days = _RECURRENCE_DAYS.get(recurrence)
    return from_date + timedelta(days=days) if days is not None else None


MAX_PROJECTED_OCCURRENCES = 400


def iter_occurrences(task: MaintenanceTask, start: datetime, end: datetime) -> Iterator[tuple[datetime, bool]]:
    """
    Échéances de la tâche dans [start, end[ : (date, projetée). La première
    est next_due_at (réelle) ; les suivantes sont projetées avec la même règle
    que compute_next_due, comme si chaque échéance était réalisée à temps.
    """
    occurrence = task.next_due_at
    projected = False
    for _ in range(MAX_PROJECTED_OCCURRENCES):
        if occurrence is None or occurrence >= end:
            return
        if occurrence >= start:
            yield occurrence, projected
        occurrence = compute_next_due(task.recurrence, task.recurrence_days, occurrence)
        projected = True
