"""
parameter_share.py (routes)

Partage des paramètres d'eau d'un aquarium par un lien public en lecture
seule : création (durée, historique montré), liste, suppression (révocation) ;
page publique /partage/parametres/<jeton> sans compte.
"""

import secrets
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from middleware.auth import min_role_required
from middleware.database import get_db
from models.aquarium import Aquarium
from models.parameter_share import ParameterShareLink
from models.water_parameter import WaterParameter
from schemas.parameter_share import ParameterShareCreate, ParameterShareRead, PublicParameters

router = APIRouter(
    prefix="/parameter-shares", tags=["Parameter shares"], dependencies=[Depends(min_role_required("consult"))]
)
public_router = APIRouter(prefix="/public/parameters", tags=["public"])
EXTRA_ROUTERS = (public_router,)

WRITE = [Depends(min_role_required("user"))]
# Pages publiques : hors des moteurs de recherche
NOINDEX = {"X-Robots-Tag": "noindex, nofollow"}


@router.get("/", response_model=List[ParameterShareRead])
def list_shares(aquarium_id: int = Query(...), db: Session = Depends(get_db)):
    return (
        db.query(ParameterShareLink)
        .filter(ParameterShareLink.aquarium_id == aquarium_id)
        .order_by(ParameterShareLink.created_at.desc())
        .all()
    )


@router.post("/", response_model=ParameterShareRead, status_code=status.HTTP_201_CREATED, dependencies=WRITE)
def create_share(payload: ParameterShareCreate, db: Session = Depends(get_db)):
    if db.get(Aquarium, payload.aquarium_id) is None:
        raise HTTPException(status_code=404, detail="Aquarium introuvable.")
    link = ParameterShareLink(
        token=secrets.token_urlsafe(18),
        aquarium_id=payload.aquarium_id,
        label=(payload.label or "").strip() or None,
        history_days=payload.history_days,
        pinned_only=payload.pinned_only,
        expires_at=datetime.now() + timedelta(days=payload.expires_in_days) if payload.expires_in_days else None,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=WRITE)
def delete_share(link_id: int, db: Session = Depends(get_db)):
    link = db.get(ParameterShareLink, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Lien introuvable.")
    db.delete(link)
    db.commit()


@public_router.get("/{token}", response_model=PublicParameters)
def public_parameters(token: str, response: Response, db: Session = Depends(get_db)):
    response.headers.update(NOINDEX)
    link = db.query(ParameterShareLink).filter(ParameterShareLink.token == token[:64]).first()
    if link is None or link.state != "active":
        raise HTTPException(status_code=404, detail="Ce lien de partage a expiré ou n'est plus valable.")
    link.view_count += 1
    link.last_viewed_at = datetime.now()
    db.commit()

    now = datetime.now()
    since = now - timedelta(days=link.history_days)
    params = (
        db.query(WaterParameter)
        .filter(WaterParameter.aquarium_id == link.aquarium_id)
        .order_by(WaterParameter.pinned.desc(), WaterParameter.name)
        .all()
    )
    aquarium = link.aquarium
    return {
        "aquarium": {
            "name": aquarium.name,
            "volume": aquarium.volume,
            "water_type": aquarium.water_type.value if hasattr(aquarium.water_type, "value") else aquarium.water_type,
            "biotope": aquarium.biotope,
        },
        "history_days": link.history_days,
        "expires_at": link.expires_at,
        "generated_at": now,
        "parameters": [
            {
                "name": p.name,
                "full_name": p.full_name,
                "unit": p.unit,
                "target_min": p.target_min,
                "target_max": p.target_max,
                "last_value": p.last_value,
                "last_reading_at": p.last_reading_at,
                "in_target": p.in_target,
                "history": [
                    {"timestamp": r.timestamp, "value": r.value} for r in p.readings if r.timestamp >= since
                ]
                if link.history_days
                else [],
            }
            for p in params
            if p.readings and (p.pinned or not link.pinned_only)
        ],
    }
