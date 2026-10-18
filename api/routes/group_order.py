"""
group_order.py (routes)

Commandes groupées (VPC) entre passionnés d'un même secteur, relayées vers
le hub de l'éditeur (services/group_orders.py). L'installation garde ses
jetons : organisateur de ses annonces, participant de celles qu'elle a
rejointes.
"""

from datetime import date
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from middleware.auth import min_role_required
from middleware.database import get_db
from models.group_order import GroupOrderLink
from services import group_orders as go

router = APIRouter(prefix="/group-orders", tags=["Group orders"], dependencies=[Depends(min_role_required("consult"))])
WRITE = [Depends(min_role_required("user"))]


class GroupOrderSettingsIO(BaseModel):
    departments: List[str] = Field(default_factory=list, max_length=10)
    notify: bool = True


class OrderIn(BaseModel):
    title: str = Field(min_length=3, max_length=80)
    shop: str = Field(min_length=2, max_length=80)
    shop_url: Optional[str] = Field(default=None, max_length=300)
    department: str = Field(min_length=2, max_length=3)
    area: str = Field(min_length=2, max_length=80)
    deadline: date
    organizer: str = Field(min_length=2, max_length=40)
    contact: str = Field(min_length=3, max_length=120)
    description: Optional[str] = Field(default=None, max_length=2000)


class OrderUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=80)
    shop: Optional[str] = Field(default=None, min_length=2, max_length=80)
    shop_url: Optional[str] = Field(default=None, max_length=300)
    area: Optional[str] = Field(default=None, min_length=2, max_length=80)
    deadline: Optional[date] = None
    contact: Optional[str] = Field(default=None, min_length=3, max_length=120)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[Literal["open", "closed", "cancelled"]] = None


class JoinItem(BaseModel):
    """Une ligne de la demande : corail / produit, lien direct chez le magasin, quantité."""

    name: str = Field(min_length=1, max_length=120)
    url: Optional[str] = Field(default=None, max_length=300)
    quantity: int = Field(default=1, ge=1, le=99)


class JoinIn(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    contact: str = Field(min_length=3, max_length=120)
    message: Optional[str] = Field(default=None, max_length=1000)
    items: list[JoinItem] = Field(default_factory=list, max_length=30)


class JoinUpdate(BaseModel):
    message: Optional[str] = Field(default=None, max_length=1000)
    items: Optional[list[JoinItem]] = Field(default=None, max_length=30)


def _with_role(order: dict, db: Session) -> dict:
    link = go.link_for(db, order["id"])
    return {**order, "my_role": link.role if link else None}


@router.get("/settings", response_model=GroupOrderSettingsIO)
def get_settings(db: Session = Depends(get_db)):
    conf = go.get_settings(db)
    return {"departments": conf.departments or [], "notify": conf.notify}


@router.put("/settings", response_model=GroupOrderSettingsIO, dependencies=WRITE)
def update_settings(payload: GroupOrderSettingsIO, db: Session = Depends(get_db)):
    from services.group_orders import enabled

    conf = go.get_settings(db)
    departments = list(dict.fromkeys(d.strip().upper() for d in payload.departments if d.strip()))
    added = set(departments) - set(conf.departments or [])
    conf.departments = departments
    conf.notify = payload.notify
    # Nouveau département : ses annonces actuelles comptent comme vues (pas d'avalanche de notifications)
    if added and enabled():
        try:
            current = go.hub("GET", "", params={"departments": ",".join(added)})
            conf.seen_ids = list(dict.fromkeys([*(conf.seen_ids or []), *(o["id"] for o in current)]))
        except HTTPException:
            pass
    db.commit()
    return {"departments": conf.departments, "notify": conf.notify}


@router.get("/")
def nearby(db: Session = Depends(get_db)):
    """Annonces en cours dans les départements suivis."""
    conf = go.get_settings(db)
    if not conf.departments:
        return []
    orders = go.hub("GET", "", params={"departments": ",".join(conf.departments)})
    return [_with_role(o, db) for o in orders]


@router.get("/mine")
def mine(db: Session = Depends(get_db)):
    """Annonces créées ici et commandes rejointes (avec contacts selon le rôle)."""
    result = []
    for link in db.query(GroupOrderLink).order_by(GroupOrderLink.created_at.desc()).all():
        try:
            order = go.hub("GET", f"/{link.hub_id}", token=link.token)
        except HTTPException as e:
            if e.status_code == 404:  # supprimée par l'organisateur ou purgée
                db.delete(link)
                db.commit()
                continue
            raise
        result.append({**order, "my_role": link.role})
    return result


@router.post("/", status_code=status.HTTP_201_CREATED, dependencies=WRITE)
def create(payload: OrderIn, db: Session = Depends(get_db)):
    order = go.hub("POST", "", json=payload.model_dump(mode="json"))
    db.add(GroupOrderLink(hub_id=order["id"], role="owner", token=order.pop("token"), title=order["title"]))
    db.commit()
    return {**order, "my_role": "owner"}


@router.get("/{hub_id}")
def detail(hub_id: str, db: Session = Depends(get_db)):
    link = go.link_for(db, hub_id)
    order = go.hub("GET", f"/{hub_id}", token=link.token if link else None)
    return {**order, "my_role": link.role if link else None}


def _owner_link(db: Session, hub_id: str) -> GroupOrderLink:
    link = go.link_for(db, hub_id)
    if link is None or link.role != "owner":
        raise HTTPException(status_code=403, detail="Seul l'organisateur peut modifier cette commande groupée.")
    return link


@router.patch("/{hub_id}", dependencies=WRITE)
def update(hub_id: str, payload: OrderUpdate, db: Session = Depends(get_db)):
    link = _owner_link(db, hub_id)
    order = go.hub("PATCH", f"/{hub_id}", token=link.token, json=payload.model_dump(mode="json", exclude_unset=True))
    link.title = order["title"]
    db.commit()
    return {**order, "my_role": "owner"}


@router.delete("/{hub_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=WRITE)
def delete(hub_id: str, db: Session = Depends(get_db)):
    link = _owner_link(db, hub_id)
    go.hub("DELETE", f"/{hub_id}", token=link.token)
    db.delete(link)
    db.commit()


@router.post("/{hub_id}/join", status_code=status.HTTP_201_CREATED, dependencies=WRITE)
def join(hub_id: str, payload: JoinIn, db: Session = Depends(get_db)):
    if go.link_for(db, hub_id) is not None:
        raise HTTPException(status_code=409, detail="Tu participes déjà à cette commande groupée (ou tu l'organises).")
    order = go.hub("POST", f"/{hub_id}/participants", json=payload.model_dump())
    db.add(GroupOrderLink(hub_id=hub_id, role="participant", token=order.pop("token"),
                          participant_id=order["members"][0]["id"], title=order["title"]))
    db.commit()
    return {**order, "my_role": "participant"}


@router.patch("/{hub_id}/join", dependencies=WRITE)
def update_join(hub_id: str, payload: JoinUpdate, db: Session = Depends(get_db)):
    """Modifier sa demande (articles, remarque) tant que la commande est ouverte."""
    link = go.link_for(db, hub_id)
    if link is None or link.role != "participant":
        raise HTTPException(status_code=404, detail="Tu ne participes pas à cette commande groupée.")
    order = go.hub("PATCH", f"/{hub_id}/participants/{link.participant_id}", token=link.token,
                   json=payload.model_dump(mode="json", exclude_unset=True))
    return {**order, "my_role": "participant"}


@router.delete("/{hub_id}/join", status_code=status.HTTP_204_NO_CONTENT, dependencies=WRITE)
def leave(hub_id: str, db: Session = Depends(get_db)):
    link = go.link_for(db, hub_id)
    if link is None or link.role != "participant":
        raise HTTPException(status_code=404, detail="Tu ne participes pas à cette commande groupée.")
    try:
        go.hub("DELETE", f"/{hub_id}/participants/{link.participant_id}", token=link.token)
    except HTTPException as e:
        if e.status_code != 404:
            raise
    db.delete(link)
    db.commit()


@router.delete("/{hub_id}/members/{participant_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=WRITE)
def remove_member(hub_id: str, participant_id: str, db: Session = Depends(get_db)):
    link = _owner_link(db, hub_id)
    go.hub("DELETE", f"/{hub_id}/participants/{participant_id}", token=link.token)


@router.post("/{hub_id}/report", status_code=status.HTTP_202_ACCEPTED, dependencies=WRITE)
def report(hub_id: str):
    return go.hub("POST", f"/{hub_id}/report")
