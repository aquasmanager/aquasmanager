"""
Stock (produits, consommables, nourriture) : quantités et seuils.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from middleware.auth import CARE_ROLES, min_role_required
from middleware.database import get_db
from services.shared_scope import apply_scope, concerns_aquarium
from models.inventory import InventoryItem, InventoryMovement
from schemas.inventory import (
    InventoryItemCreate,
    InventoryItemRead,
    InventoryItemUpdate,
    InventoryMovementCreate,
    InventoryMovementRead,
)

router = APIRouter(prefix="/inventory-items", tags=["Inventory"], dependencies=[Depends(min_role_required("consult"))])


@router.get("/", response_model=List[InventoryItemRead])
def list_items(
    aquarium_id: Optional[int] = Query(None, description="Articles concernant cet aquarium (tous si absent)"),
    db: Session = Depends(get_db),
):
    query = db.query(InventoryItem)
    if aquarium_id is not None:
        query = query.filter(concerns_aquarium(InventoryItem, aquarium_id))
    return query.order_by(InventoryItem.name).all()


@router.post(
    "/",
    response_model=InventoryItemRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user"))],
)
def create_item(item_in: InventoryItemCreate, db: Session = Depends(get_db)):
    item = InventoryItem(**item_in.model_dump(exclude={"scope", "aquarium_ids"}))
    apply_scope(db, item, item_in.scope, item_in.aquarium_ids, item_in.aquarium_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch(
    "/{item_id}",
    response_model=InventoryItemRead,
    dependencies=[Depends(min_role_required("user"))],
)
def update_item(item_id: int, update_data: InventoryItemUpdate, db: Session = Depends(get_db)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Article non trouvé")

    changes = update_data.model_dump(exclude_unset=True, exclude={"scope", "aquarium_ids"})
    for field, value in changes.items():
        setattr(item, field, value)
    if update_data.scope is not None:
        apply_scope(db, item, update_data.scope, update_data.aquarium_ids, item.aquarium_id)

    db.commit()
    db.refresh(item)
    return item


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("manager"))],
)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Article non trouvé")

    db.delete(item)
    db.commit()


@router.get("/{item_id}/movements", response_model=List[InventoryMovementRead])
def list_movements(item_id: int, db: Session = Depends(get_db)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Article non trouvé")

    return (
        db.query(InventoryMovement)
        .filter(InventoryMovement.item_id == item_id)
        .order_by(InventoryMovement.created_at.desc())
        .all()
    )


@router.post(
    "/{item_id}/movements",
    response_model=InventoryItemRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user", also=CARE_ROLES))],
)
def create_movement(item_id: int, movement_in: InventoryMovementCreate, db: Session = Depends(get_db)):
    """Ajoute un mouvement (réappro positif / consommation négatif) et
    renvoie l'article avec sa quantité à jour."""
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Article non trouvé")

    db.add(InventoryMovement(item_id=item_id, delta=movement_in.delta, note=movement_in.note))
    # Arrondi : des additions de décimaux donnaient 12.199999999999 au lieu de 12,2
    item.quantity = round(item.quantity + movement_in.delta, 6)

    db.commit()
    db.refresh(item)
    return item
