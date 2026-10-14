"""
Rappel des tâches du jour : chaque matin à task_reminder_hour (heure locale),
un seul message regroupe les tâches dont l'échéance tombe aujourd'hui
(changement d'eau, résine...). Une tâche n'est rappelée qu'une fois par jour.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session
from datetime import datetime

from models.aquarium import Aquarium
from models.maintenance_task import MaintenanceTask
from services.maintenance_task import is_due_today, local_now
from services.shared_scope import scope_label
from settings import settings

logger = logging.getLogger(__name__)


def send_due_today_reminders(db: Session, now: Optional[datetime] = None) -> int:
    from services.notify import dispatch_alert

    now = now or local_now()
    if now.hour < settings.task_reminder_hour:
        return 0
    today = now.date()
    tasks = [
        task
        for task in db.query(MaintenanceTask).filter(MaintenanceTask.next_due_at.isnot(None)).all()
        if is_due_today(task.next_due_at, now) and task.reminder_sent_on != today
    ]
    if not tasks:
        return 0

    names = {a.id: a.name for a in db.query(Aquarium).all()}
    lines = []
    for task in sorted(tasks, key=lambda t: (scope_label(t, names), t.title)):
        line = f"• {scope_label(task, names)} — {task.title}"
        if task.description:
            line += f" ({task.description.strip()[:80]})"
        lines.append(line)
        task.reminder_sent_on = today

    title = "[AquasManager] Tâche du jour" if len(tasks) == 1 else f"[AquasManager] {len(tasks)} tâches du jour"
    dispatch_alert(title, "\n".join(lines), priority="default")
    db.commit()
    logger.info("Rappel des tâches du jour envoyé (%s tâche(s))", len(tasks))
    return len(tasks)
