"""
frag.py (routes)

Boutures de coraux.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from middleware.auth import FRAG_ROLES, min_role_required
from middleware.database import get_db
from models.aquarium import Aquarium
from models.coral import Coral
from models.frag import Frag, FragMovement
from models.photo import PhotoType
from schemas.frag import (
    FragMove,
    FragCreate,
    FragMovementRead,
    FragMovementUpdate,
    FragRead,
    FragStatRow,
    FragStatus,
    FragUpdate,
)
from services.cleanup import delete_photos
from services.frag_labels import render_labels
from services.frags import attach_counts, frag_stats, log_movement, next_number, refresh_frag_status

# Gestion des boutures ouverte à tous ; la vente (cessions, vitrine) relève de la bourse
router = APIRouter(prefix="/frags", tags=["frags"], dependencies=[Depends(min_role_required("consult"))])


def _get_or_404(db: Session, frag_id: int) -> Frag:
    frag = db.get(Frag, frag_id)
    if not frag:
        raise HTTPException(status_code=404, detail="Bouture non trouvée")
    return frag


def _log_move(db: Session, frag: Frag, new_aquarium_id: Optional[int]) -> None:
    """Changement de bac tracé dans l'historique du lot (« Bac A → Bac boutures »)."""
    def name(aquarium_id: Optional[int]) -> str:
        aquarium = db.get(Aquarium, aquarium_id) if aquarium_id else None
        return aquarium.name if aquarium else "hors bac"

    log_movement(db, frag, 0, "moved", f"{name(frag.aquarium_id)} → {name(new_aquarium_id)}")


def _check_aquarium(db: Session, aquarium_id: Optional[int]) -> None:
    if aquarium_id is not None and db.get(Aquarium, aquarium_id) is None:
        raise HTTPException(status_code=400, detail="Aquarium inconnu.")


@router.get("/", response_model=List[FragRead])
def list_frags(
    status_filter: Optional[FragStatus] = Query(None, alias="status"),
    aquarium_id: Optional[int] = Query(None),
    mother_coral_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Frag)
    if status_filter:
        query = query.filter(Frag.status == status_filter)
    if aquarium_id is not None:
        query = query.filter(Frag.aquarium_id == aquarium_id)
    if mother_coral_id is not None:
        query = query.filter(Frag.mother_coral_id == mother_coral_id)
    return attach_counts(db, query.order_by(Frag.cut_date.desc(), Frag.reference.desc()).all())


@router.get("/stats", response_model=List[FragStatRow])
def stats(group_by: str = Query("species", pattern="^(species|mother)$"), db: Session = Depends(get_db)):
    """Suivi par espèce ou par pied mère : produites, cédées, perdues, taux de survie."""
    return frag_stats(db, group_by)


@router.get("/labels.pdf")
def labels(
    base_url: str = Query(..., pattern=r"^https?://", description="Adresse de l'appli (lien des QR codes)"),
    ids: Optional[str] = Query(None, description="Lots à imprimer (ex : 3,7,12) ; lots disponibles si absent"),
    per_unit: bool = Query(False, description="Une étiquette par bouture plutôt que par lot"),
    db: Session = Depends(get_db),
):
    query = db.query(Frag)
    if ids:
        try:
            wanted = [int(i) for i in ids.split(",") if i.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="Liste de lots invalide.")
        order = {frag_id: rank for rank, frag_id in enumerate(wanted)}
        frags = sorted(query.filter(Frag.id.in_(wanted)).all(), key=lambda f: order[f.id])
    else:
        frags = query.filter(Frag.quantity > 0).order_by(Frag.name, Frag.reference).all()
    return Response(
        render_labels(frags, base_url, per_unit),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="etiquettes-boutures.pdf"'},
    )


@router.get("/{frag_id}", response_model=FragRead)
def get_frag(frag_id: int, db: Session = Depends(get_db)):
    return attach_counts(db, [_get_or_404(db, frag_id)])[0]


@router.post(
    "/move",
    response_model=List[FragRead],
    dependencies=[Depends(min_role_required("user", also=FRAG_ROLES))],
)
def move_frags(payload: FragMove, db: Session = Depends(get_db)):
    """Déplace plusieurs lots vers un bac (ex : retour de bourse, bac de boutures)."""
    _check_aquarium(db, payload.aquarium_id)
    frags = db.query(Frag).filter(Frag.id.in_(payload.frag_ids)).all()
    if len(frags) != len(set(payload.frag_ids)):
        raise HTTPException(status_code=404, detail="Bouture introuvable.")
    for frag in frags:
        if frag.aquarium_id != payload.aquarium_id:
            _log_move(db, frag, payload.aquarium_id)
            frag.aquarium_id = payload.aquarium_id
    db.commit()
    return attach_counts(db, frags)


@router.post(
    "/",
    response_model=FragRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user", also=FRAG_ROLES))],
)
def create_frag(frag_in: FragCreate, db: Session = Depends(get_db)):
    """Crée un lot de boutures ; les champs absents viennent du pied mère."""
    mother = None
    if frag_in.mother_coral_id is not None:
        mother = db.get(Coral, frag_in.mother_coral_id)
        if mother is None:
            raise HTTPException(status_code=400, detail="Corail d'origine inconnu.")
    aquarium_id = frag_in.aquarium_id or (mother.aquarium_id if mother else None)
    _check_aquarium(db, aquarium_id)

    def pick(value, fallback):
        return value if value not in (None, "") else fallback

    name = pick(frag_in.name, mother.name if mother else None)
    if not name:
        raise HTTPException(status_code=400, detail="Indique le nom de la bouture ou son corail d'origine.")
    values = dict(
        aquarium_id=aquarium_id,
        mother_coral_id=mother.id if mother else None,
        mother_name=mother.name if mother else None,
        name=name,
        scientific_name=pick(frag_in.scientific_name, mother.scientific_name if mother else "") or "",
        coral_type=pick(frag_in.coral_type, mother.type.value if mother else None),
        cites=pick(frag_in.cites, mother.cites if mother else "") or "",
        origin=pick(frag_in.origin, mother.origin if mother else "") or "",
        acquired_from=pick(frag_in.acquired_from, mother.acquired_from if mother else None),
        price=frag_in.price,
        notes=frag_in.notes,
        quantity=frag_in.quantity,
    )
    if frag_in.cut_date:
        values["cut_date"] = frag_in.cut_date

    frag = Frag(reference=next_number(db, Frag.reference, "B"), status="available", **values)
    db.add(frag)
    db.flush()
    log_movement(db, frag, frag.quantity, "created")
    db.commit()
    db.refresh(frag)
    return frag


@router.patch("/{frag_id}", response_model=FragRead, dependencies=[Depends(min_role_required("user", also=FRAG_ROLES))])
def update_frag(frag_id: int, update_data: FragUpdate, db: Session = Depends(get_db)):
    frag = _get_or_404(db, frag_id)
    changes = update_data.model_dump(exclude_unset=True, exclude={"quantity_reason", "quantity_note"})
    if "aquarium_id" in changes:
        _check_aquarium(db, changes["aquarium_id"])
    if "quantity" in changes:
        log_movement(db, frag, changes["quantity"] - frag.quantity, update_data.quantity_reason, update_data.quantity_note)
    if "aquarium_id" in changes and changes["aquarium_id"] != frag.aquarium_id:
        _log_move(db, frag, changes["aquarium_id"])
    for field, value in changes.items():
        setattr(frag, field, value)
    if "quantity" in changes:
        refresh_frag_status(db, frag)
    db.commit()
    db.refresh(frag)
    return attach_counts(db, [frag])[0]


@router.get("/{frag_id}/movements", response_model=List[FragMovementRead])
def list_movements(frag_id: int, db: Session = Depends(get_db)):
    _get_or_404(db, frag_id)
    return (
        db.query(FragMovement)
        .filter(FragMovement.frag_id == frag_id)
        .order_by(FragMovement.created_at.desc(), FragMovement.id.desc())
        .all()
    )


@router.patch(
    "/{frag_id}/movements/{movement_id}",
    response_model=FragMovementRead,
    dependencies=[Depends(min_role_required("user", also=FRAG_ROLES))],
)
def update_movement(frag_id: int, movement_id: int, update: FragMovementUpdate, db: Session = Depends(get_db)):
    movement = db.get(FragMovement, movement_id)
    if movement is None or movement.frag_id != frag_id:
        raise HTTPException(status_code=404, detail="Mouvement non trouvé")
    if update.reason and movement.reason not in ("added", "lost", "gift", "correction"):
        raise HTTPException(status_code=409, detail="Ce mouvement vient d'un certificat ou de la création du lot.")
    changes = update.model_dump(exclude_unset=True)
    reason = changes.get("reason")
    if (reason == "added" and movement.delta < 0) or (reason in ("lost", "gift") and movement.delta > 0):
        raise HTTPException(status_code=400, detail="Raison incompatible avec le sens du mouvement.")
    for field, value in changes.items():
        setattr(movement, field, value)
    db.commit()
    db.refresh(movement)
    return movement


@router.delete("/{frag_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(min_role_required("manager", also=FRAG_ROLES))])
def delete_frag(frag_id: int, db: Session = Depends(get_db)):
    frag = _get_or_404(db, frag_id)
    if attach_counts(db, [frag])[0].reserved_quantity:
        raise HTTPException(status_code=409, detail="Bouture dans un certificat en attente de signature : supprime d'abord le certificat.")
    delete_photos(db, PhotoType.frags, frag.id)
    db.delete(frag)
    db.commit()
