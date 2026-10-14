"""
Tâches d'entretien récurrentes et calendrier.
"""

from datetime import date, datetime, time, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from middleware.auth import CARE_ROLES, min_role_required
from middleware.database import get_db
from models.aquarium import Aquarium
from models.maintenance_task import MaintenanceTask, MaintenanceTaskCompletion
from schemas.maintenance_task import (
    MaintenanceTaskCreate,
    MaintenanceTaskRead,
    MaintenanceTaskUpdate,
    MaintenanceTaskCompletionCreate,
    MaintenanceTaskCompletionRead,
    CalendarEventRead,
)
from services.maintenance_task import compute_next_due, is_overdue, iter_occurrences
from services.shared_scope import apply_scope, concerns_aquarium, scope_label

router = APIRouter(
    prefix="/maintenance-tasks", tags=["Maintenance Tasks"], dependencies=[Depends(min_role_required("consult"))]
)


@router.get("/", response_model=List[MaintenanceTaskRead])
def list_tasks(
    aquarium_id: Optional[int] = Query(None, description="Tâches concernant cet aquarium (toutes si absent)"),
    db: Session = Depends(get_db),
):
    query = db.query(MaintenanceTask)
    if aquarium_id is not None:
        query = query.filter(concerns_aquarium(MaintenanceTask, aquarium_id))
    return query.order_by(MaintenanceTask.title).all()


CALENDAR_MAX_DAYS = 100


@router.get("/calendar", response_model=List[CalendarEventRead])
def get_calendar(
    start: date = Query(..., description="Premier jour inclus (YYYY-MM-DD)"),
    end: date = Query(..., description="Dernier jour inclus (YYYY-MM-DD)"),
    aquarium_id: Optional[int] = Query(None, description="Tous les aquariums si absent"),
    db: Session = Depends(get_db),
):
    """
    Évènements de toutes les tâches sur la période : échéances ("due", en
    retard si passée), occurrences futures des tâches récurrentes
    ("planned") et réalisations ("done").
    """
    if end < start or (end - start).days > CALENDAR_MAX_DAYS:
        raise HTTPException(status_code=400, detail=f"Période invalide ({CALENDAR_MAX_DAYS} jours maximum).")
    start_dt = datetime.combine(start, time.min)
    end_dt = datetime.combine(end + timedelta(days=1), time.min)

    names = {a.id: a.name for a in db.query(Aquarium).all()}
    query = db.query(MaintenanceTask)
    if aquarium_id is not None:
        query = query.filter(concerns_aquarium(MaintenanceTask, aquarium_id))

    events = []
    for task in query.all():
        base = {
            "task_id": task.id,
            "title": task.title,
            "aquarium_id": task.aquarium_id,
            "aquarium_name": scope_label(task, names),
            "aquarium_ids": task.aquarium_ids,
            "shared": task.scope != "single",
        }
        for occurrence, projected in iter_occurrences(task, start_dt, end_dt):
            events.append({
                **base,
                "kind": "planned" if projected else "due",
                "date": occurrence,
                "overdue": not projected and is_overdue(occurrence),
            })
        for completion in task.completions:
            if start_dt <= completion.completed_at < end_dt:
                events.append({**base, "kind": "done", "date": completion.completed_at, "note": completion.note})

    return sorted(events, key=lambda e: (e["date"], e["title"]))


@router.post(
    "/",
    response_model=MaintenanceTaskRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user"))],
)
def create_task(task_in: MaintenanceTaskCreate, db: Session = Depends(get_db)):
    task = MaintenanceTask(**task_in.model_dump(exclude={"scope", "aquarium_ids"}))
    apply_scope(db, task, task_in.scope, task_in.aquarium_ids, task_in.aquarium_id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch(
    "/{task_id}",
    response_model=MaintenanceTaskRead,
    dependencies=[Depends(min_role_required("user"))],
)
def update_task(task_id: int, update_data: MaintenanceTaskUpdate, db: Session = Depends(get_db)):
    task = db.query(MaintenanceTask).filter(MaintenanceTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")

    for field, value in update_data.model_dump(exclude_unset=True, exclude={"scope", "aquarium_ids"}).items():
        setattr(task, field, value)
    if update_data.scope is not None:
        apply_scope(db, task, update_data.scope, update_data.aquarium_ids, task.aquarium_id)

    db.commit()
    db.refresh(task)
    return task


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("manager"))],
)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(MaintenanceTask).filter(MaintenanceTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")

    db.delete(task)
    db.commit()


@router.post(
    "/{task_id}/complete",
    response_model=MaintenanceTaskRead,
    dependencies=[Depends(min_role_required("user", also=CARE_ROLES))],
)
def complete_task(task_id: int, completion_in: MaintenanceTaskCompletionCreate, db: Session = Depends(get_db)):
    """
    Journalise une réalisation de la tâche et recalcule son échéance
    suivante si elle est récurrente (sinon next_due_at repasse à null : la
    tâche ne réapparaît plus tant qu'elle n'est pas rééditée).
    """
    task = db.query(MaintenanceTask).filter(MaintenanceTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")

    completed_at = completion_in.completed_at or datetime.now()
    db.add(MaintenanceTaskCompletion(task_id=task_id, completed_at=completed_at, note=completion_in.note))

    task.last_completed_at = completed_at
    task.next_due_at = compute_next_due(task.recurrence, task.recurrence_days, completed_at)

    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}/completions", response_model=List[MaintenanceTaskCompletionRead])
def list_completions(task_id: int, db: Session = Depends(get_db)):
    task = db.query(MaintenanceTask).filter(MaintenanceTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")

    return (
        db.query(MaintenanceTaskCompletion)
        .filter(MaintenanceTaskCompletion.task_id == task_id)
        .order_by(MaintenanceTaskCompletion.completed_at.desc())
        .all()
    )


@router.delete(
    "/{task_id}/completions/{completion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("manager"))],
)
def delete_completion(task_id: int, completion_id: int, db: Session = Depends(get_db)):
    completion = (
        db.query(MaintenanceTaskCompletion)
        .filter(MaintenanceTaskCompletion.id == completion_id, MaintenanceTaskCompletion.task_id == task_id)
        .first()
    )
    if not completion:
        raise HTTPException(status_code=404, detail="Complétion non trouvée")

    db.delete(completion)
    db.flush()

    # Recale last_completed_at si on vient de supprimer la plus récente
    # (correction d'une saisie erronée) ; next_due_at n'est volontairement
    # pas retouché ici (pas de façon fiable de savoir s'il a été ajusté
    # manuellement depuis).
    task = db.query(MaintenanceTask).filter(MaintenanceTask.id == task_id).first()
    if task:
        remaining = (
            db.query(MaintenanceTaskCompletion)
            .filter(MaintenanceTaskCompletion.task_id == task_id)
            .order_by(MaintenanceTaskCompletion.completed_at.desc())
            .first()
        )
        task.last_completed_at = remaining.completed_at if remaining else None

    db.commit()
