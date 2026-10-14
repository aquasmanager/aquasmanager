"""
Coraux des aquariums (fiche, photos, documents CITES).
"""

import logging
from services.cites_links import link_documents_to_coral, normalize
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from middleware.auth import min_role_required
from models.coral import Coral
from models.frag import Frag
from schemas.coral import CoralRead, CoralCreate, CoralUpdate, CoralListResponse
from middleware.database import get_db
from models.photo import PhotoType
from services.cleanup import delete_photos
from services import journal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/corals", tags=["corals"], dependencies=[Depends(min_role_required("consult"))])


@router.post(
    "/",
    response_model=CoralRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user"))],
)
def create_coral(coral_in: CoralCreate, db: Session = Depends(get_db)):
    try:
        db_coral = Coral(**coral_in.model_dump())
        db.add(db_coral)
        db.flush()
        # Documents d'achat portant ce numéro CITES : liés automatiquement
        link_documents_to_coral(db, db_coral)
        journal.livestock_added(db, db_coral.aquarium_id, db_coral.name, db_coral.quantity, db_coral.date_acquisition)
        db.commit()
        db.refresh(db_coral)
        return db_coral
    except Exception:
        logger.exception("Erreur lors de l'ajout d'un corail")
        raise


@router.patch(
    "/{coral_id}",
    response_model=CoralRead,
    dependencies=[Depends(min_role_required("user"))],
)
def update_coral(coral_id: int, update_data: CoralUpdate, db: Session = Depends(get_db)):
    try:
        coral = db.query(Coral).filter(Coral.id == coral_id).first()
        if not coral:
            raise HTTPException(status_code=404, detail="Corail non trouvé")

        updated = False
        old_cites = normalize(coral.cites)
        for field, value in update_data.model_dump(exclude_unset=True).items():
            if getattr(coral, field) != value:
                setattr(coral, field, value)
                updated = True
        if normalize(coral.cites) != old_cites:
            link_documents_to_coral(db, coral)

        if updated:
            db.commit()
            db.refresh(coral)

        return coral
    except Exception:
        logger.exception("Erreur lors de la mise à jour du corail")
        raise


@router.delete(
    "/{coral_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("manager"))],
)
def delete_coral(coral_id: int, db: Session = Depends(get_db)):
    try:
        coral = db.query(Coral).filter(Coral.id == coral_id).first()
        if not coral:
            raise HTTPException(status_code=404, detail="Corail non trouvé")

        delete_photos(db, PhotoType.corals, coral_id)
        # Les boutures gardent les infos copiées du pied mère
        db.query(Frag).filter(Frag.mother_coral_id == coral_id).update(
            {Frag.mother_coral_id: None}, synchronize_session=False
        )
        db.delete(coral)
        db.commit()
        return
    except Exception:
        logger.exception("Erreur lors de la suppression du corail")
        raise


@router.get("/{coral_id}", response_model=CoralRead)
def get_coral(coral_id: int, db: Session = Depends(get_db)):
    try:
        coral = db.query(Coral).filter(Coral.id == coral_id).first()
        if not coral:
            raise HTTPException(status_code=404, detail="Corail non trouvé")
        return coral
    except Exception:
        logger.exception("Erreur lors de la récupération du corail")
        raise


@router.get("/", response_model=CoralListResponse)
def list_corals(
    aquarium_id: Optional[int] = Query(None, description="Coraux de cet aquarium (tous si absent)"),
    db: Session = Depends(get_db),
):
    try:
        query = db.query(Coral)
        if aquarium_id is not None:
            query = query.filter(Coral.aquarium_id == aquarium_id)
        corals = query.order_by(Coral.name).all()
        total = len(corals)
        return {"total": total, "corals": corals}
    except Exception:
        logger.exception("Erreur lors du listage des coraux")
        raise