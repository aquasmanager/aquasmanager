"""
user.py (routes)

Gestion des utilisateurs (liste, modification, reset de mot de passe,
suppression). La création se fait toujours via /register (routes/auth.py).
Réservé aux admins.
"""

import logging
from typing import List

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from middleware.auth import get_current_identity, min_role_required
from middleware.database import get_db
from models.refresh_token import RefreshToken
from models.user import User, UserRole
from schemas.user import UserPasswordReset, UserRead, UserUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(min_role_required("admin"))])


def _admin_count(db: Session) -> int:
    return db.query(User).filter(User.role == UserRole.admin).count()


@router.get("/", response_model=List[UserRead])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.username).all()


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: int, update_data: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    update_dict = update_data.model_dump(exclude_unset=True)

    if "username" in update_dict and update_dict["username"] != user.username:
        existing = db.query(User).filter(User.username == update_dict["username"]).first()
        if existing:
            raise HTTPException(status_code=400, detail="Nom d'utilisateur déjà utilisé")
        user.username = update_dict["username"]

    if "role" in update_dict and update_dict["role"] != user.role.value:
        # Empêche de se retrouver sans aucun compte admin en base.
        if user.role == UserRole.admin and _admin_count(db) <= 1:
            raise HTTPException(
                status_code=400,
                detail="Impossible de retirer le rôle admin du dernier administrateur.",
            )
        user.role = update_dict["role"]

    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/reset-password", response_model=UserRead)
def reset_password(user_id: int, payload: UserPasswordReset, db: Session = Depends(get_db)):
    """
    Réinitialise le mot de passe d'un utilisateur (l'admin choisit une
    valeur temporaire). Par défaut (must_change_password), l'intéressé devra
    le changer lui-même via /change-password à sa prochaine connexion.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    user.password = bcrypt.hashpw(payload.new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user.must_change_password = payload.must_change_password
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    identity: dict = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if identity.get("user_id") == user_id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte.")

    if user.role == UserRole.admin and _admin_count(db) <= 1:
        raise HTTPException(status_code=400, detail="Impossible de supprimer le dernier administrateur.")

    # Déconnecte l'utilisateur partout (les jetons ne partent pas en cascade sous SQLite)
    db.query(RefreshToken).filter(RefreshToken.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()
