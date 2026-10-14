"""
Cartes du tableau de bord d'un aquarium (ajout, ordre, réglages).
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from middleware.auth import min_role_required
from middleware.database import get_db
from models.dashboard_card import DashboardCard
from schemas.dashboard_card import DashboardCardCreate, DashboardCardOrder, DashboardCardRead, DashboardCardUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard-cards", tags=["Dashboard"], dependencies=[Depends(min_role_required("consult"))])


@router.get("/", response_model=List[DashboardCardRead])
def list_dashboard_cards(aquarium_id: int = Query(...), db: Session = Depends(get_db)):
    return (
        db.query(DashboardCard)
        .filter(DashboardCard.aquarium_id == aquarium_id)
        .order_by(DashboardCard.position)
        .all()
    )


@router.post(
    "/",
    response_model=DashboardCardRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user"))],
)
def create_dashboard_card(card_in: DashboardCardCreate, db: Session = Depends(get_db)):
    # Append en fin de grille pour cet aquarium.
    max_position: Optional[int] = (
        db.query(func.max(DashboardCard.position))
        .filter(DashboardCard.aquarium_id == card_in.aquarium_id)
        .scalar()
    )
    card = DashboardCard(**card_in.model_dump(), position=(max_position or 0) + 1)
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.put(
    "/order",
    response_model=List[DashboardCardRead],
    dependencies=[Depends(min_role_required("user"))],
)
def reorder_dashboard_cards(order: DashboardCardOrder, db: Session = Depends(get_db)):
    """Réorganisation par glisser-déposer : positions 1, 2, 3... dans l'ordre reçu."""
    cards = {c.id: c for c in db.query(DashboardCard).filter(DashboardCard.aquarium_id == order.aquarium_id)}
    if set(order.ids) - set(cards):
        raise HTTPException(status_code=400, detail="Carte inconnue pour cet aquarium")
    # Cartes absentes de la liste (ajoutées entre-temps) : gardées à la fin
    ordered = [cards[i] for i in order.ids] + sorted(
        (c for i, c in cards.items() if i not in order.ids), key=lambda c: c.position
    )
    for position, card in enumerate(ordered, start=1):
        card.position = position
    db.commit()
    return ordered


@router.patch(
    "/{card_id}",
    response_model=DashboardCardRead,
    dependencies=[Depends(min_role_required("user"))],
)
def update_dashboard_card(card_id: int, update_data: DashboardCardUpdate, db: Session = Depends(get_db)):
    card = db.query(DashboardCard).filter(DashboardCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Carte non trouvée")

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(card, field, value)

    db.commit()
    db.refresh(card)
    return card


@router.delete(
    "/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("user"))],
)
def delete_dashboard_card(card_id: int, db: Session = Depends(get_db)):
    card = db.query(DashboardCard).filter(DashboardCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Carte non trouvée")

    db.delete(card)
    db.commit()
