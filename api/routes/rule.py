"""
Règles d'automatisation (création, modification, activation).
"""

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
import logging
from middleware.auth import min_role_required
from middleware.database import get_db
from schemas.rule import RuleCreate, RuleRead, RuleUpdate
from services.rule import create_rule_service, delete_rule_service, update_rule_service
from models.rule import Rule

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rules", tags=["Rules"], dependencies=[Depends(min_role_required("consult"))])


@router.post(
    "/",
    response_model=RuleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("manager"))],
)
def create_rule(rule_in: RuleCreate, db: Session = Depends(get_db)):
    """
    Crée une nouvelle règle d'automatisation avec ses conditions et sa minuterie.
    """
    try:
        return create_rule_service(db=db, rule_in=rule_in)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Erreur inattendue lors de la création de la règle")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne lors de la création de la règle"
        )


@router.get("/", response_model=List[RuleRead])
def get_rules(db: Session = Depends(get_db)):
    """
    Récupère la liste de toutes les règles configurées.
    """
    return db.query(Rule).all()


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("manager"))],
)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    """
    Supprime une règle d'automatisation.
    """
    delete_rule_service(db=db, rule_id=rule_id)
    return None # 204 No Content ne renvoie pas de corps

@router.patch(
    "/{rule_id}",
    response_model=RuleRead,
    dependencies=[Depends(min_role_required("manager"))],
)
def update_rule(rule_id: int, rule_in: RuleUpdate, db: Session = Depends(get_db)):
    """
    Met à jour partiellement une règle d'automatisation (change cible, action, conditions, etc.).
    """
    try:
        return update_rule_service(db=db, rule_id=rule_id, rule_in=rule_in)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Erreur inattendue lors de la mise à jour de la règle")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne lors de la mise à jour de la règle"
        )