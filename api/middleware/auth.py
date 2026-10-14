"""
Authentification : jetons JWT d'accès, jetons de rafraîchissement (cookie)
et contrôle des rôles sur les routes (min_role_required).
"""

import hashlib
import logging
from typing import Optional
from fastapi import HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from datetime import timedelta, datetime
import jwt
from sqlalchemy.orm import Session

from middleware.database import get_db
from models.refresh_token import RefreshToken
from settings import settings
import secrets

logger = logging.getLogger(__name__)

SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTE = 15
REFRESH_TOKEN_EXPIRE_DAY = 7

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

ROLE = settings.role


# Helper JWT
def create_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_access_token(user_id: int, username: str, role: str):
    access_token = create_token(
        {"user_id": user_id, "username": username, "role": role, "type": "access"},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTE),
    )

    return access_token


def create_refesh_token(user_id: int, db: Session):
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAY)

    db_token = RefreshToken(user_id=user_id, token=token_hash, expires_at=expires_at)
    db.add(db_token)
    db.commit()
    db.refresh(db_token)

    return raw_token


def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Type du token invalide")
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token invalide")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalide")
    return payload


def verify_refresh_token(token: str, db: Session):
    db_token = db.query(RefreshToken).filter_by(token=token).first()
    if not db_token or db_token.expires_at < datetime.utcnow() or db_token.user is None:
        raise HTTPException(status_code=401, detail="Refresh token invalide ou expiré")
    return db_token.user


def purge_expired_refresh_tokens(db: Session) -> int:
    """Supprime les refresh tokens expirés (un par connexion, jamais nettoyés sinon)."""
    deleted = db.query(RefreshToken).filter(RefreshToken.expires_at < datetime.utcnow()).delete(synchronize_session=False)
    db.commit()
    return deleted


def get_current_identity(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Récupère le payload du JWT
    """
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token invalide")

    payload["type"] = "user"
    return payload


# Rôles autorisés en plus du niveau minimal sur les boutures et cessions
FRAG_ROLES = ("seller",)
# Gardiennage : cocher les tâches, saisir les relevés, noter les consommations du stock
CARE_ROLES = ("caretaker",)


def min_role_required(min_role: str, also: tuple[str, ...] = ()):
    """Niveau minimal requis ; « also » : rôles acceptés en plus quel que soit leur niveau."""

    def role_checker(identity: dict = Depends(get_current_identity)):
        role = identity.get("role")
        if role is None:
            raise HTTPException(status_code=401, detail="Rôle non défini")
        if role in also:
            return identity

        user_level = ROLE.get(role, 0)
        min_level = ROLE.get(min_role, 0)

        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=f"Accès interdit. Il faut au minimum le rôle: {min_role}"
            )
        return identity

    return role_checker