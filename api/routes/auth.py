"""
Authentification : inscription, connexion (limitée contre la force brute),
déconnexion et rafraîchissement de session.
"""

import hashlib
import time
from collections import defaultdict, deque
import logging
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from middleware.database import get_db
import bcrypt
from middleware.auth import (
    oauth2_scheme,
    verify_refresh_token,
    create_access_token,
    create_refesh_token,
    verify_access_token,
    get_current_identity,
    min_role_required,
)
from models.refresh_token import RefreshToken
from settings import settings
from models.user import User
from schemas.user import UserRead, UserCreate, PasswordChange, LanguageChange

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("admin"))],
)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Crée un nouvel utilisateur. Réservé aux administrateurs : il n'existe plus
    d'auto-inscription publique.
    """
    try:
        db_user = db.query(User).filter(User.username == user_in.username).first()

        if db_user:
            raise HTTPException(status_code=400, detail="Nom d'utilisateur déjà utilisé")

        hashed_pw = bcrypt.hashpw(user_in.password.encode("utf-8"), bcrypt.gensalt())

        db_user = User(
            username=user_in.username,
            password=hashed_pw.decode("utf-8"),
            role=user_in.role,
            must_change_password=user_in.must_change_password,
        )

        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except HTTPException:
        raise
    except Exception:
        logger.exception("Erreur lors de l'enregistrement de l'utilisateur")
        raise


# Anti-force brute : 5 échecs en 15 min pour une même adresse IP ou un même
# identifiant bloquent 15 min (mémoire du processus, suffisant pour un serveur)
LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 15 * 60
_login_failures: dict[str, deque] = defaultdict(deque)
# Hash factice : même durée de vérification que l'identifiant existe ou non
_DUMMY_HASH = bcrypt.hashpw(b"aquasmanager", bcrypt.gensalt())


def _recent_failures(key: str, now: float) -> deque:
    failures = _login_failures[key]
    while failures and now - failures[0] > LOGIN_WINDOW_SECONDS:
        failures.popleft()
    return failures


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    now = time.monotonic()
    keys = [f"ip:{request.client.host if request.client else '?'}", f"user:{form_data.username.lower()}"]
    if any(len(_recent_failures(key, now)) >= LOGIN_MAX_FAILURES for key in keys):
        raise HTTPException(status_code=429, detail="Trop de tentatives de connexion. Réessaie dans 15 minutes.")

    user = db.query(User).filter(User.username == form_data.username).first()
    stored = user.password.encode("utf-8") if user else _DUMMY_HASH
    if not bcrypt.checkpw(form_data.password.encode("utf-8"), stored) or not user:
        for key in keys:
            _login_failures[key].append(now)
        raise HTTPException(status_code=400, detail="Identifiants invalides")
    for key in keys:
        _login_failures.pop(key, None)

    access = create_access_token(user_id=user.id, username=user.username, role=user.role.value)
    refresh = create_refesh_token(user_id=user.id, db=db)

    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        secure=settings.auth.cookie_secure,
        samesite=settings.auth.cookie_samesite,
        max_age=60 * 60 * 24 * 7,
        path="/",
        # partitioned=True
    )

    return {
        "access_token": access,
        "role": user.role.value,
        "must_change_password": user.must_change_password,
        "language": user.language,
    }


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(status_code=401, detail="Pas de refresh token")

    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    db_token = db.query(RefreshToken).filter(RefreshToken.token == token_hash).first()
    if db_token:
        db.delete(db_token)
        db.commit()

    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=settings.auth.cookie_secure,
        samesite=settings.auth.cookie_samesite,
        path="/",
        # partitioned=True
    )

    return {"message": "Déconnecté avec succès"}


@router.post("/refresh")
def refresh_token(request: Request, db: Session = Depends(get_db)):
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(status_code=401, detail="Pas de refresh token")

    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    user = verify_refresh_token(token=token_hash, db=db)

    new_access = create_access_token(user_id=user.id, username=user.username, role=user.role.value)

    return {"access_token": new_access}


@router.get("/me")
def read_me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = verify_access_token(token)
    user = db.query(User).filter(User.id == payload.get("user_id")).first()
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    return {
        "user_id": user.id,
        "username": user.username,
        "role": user.role.value,
        "must_change_password": user.must_change_password,
        "language": user.language,
    }


@router.put("/me/language")
def change_language(payload: LanguageChange, identity: dict = Depends(get_current_identity), db: Session = Depends(get_db)):
    """Langue de l'interface, gardée pour les prochaines connexions (autres appareils compris)."""
    user = db.query(User).filter(User.id == identity.get("user_id")).first()
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    user.language = payload.language
    db.commit()
    return {"language": user.language}


@router.post("/change-password")
def change_password(
    payload: PasswordChange,
    identity: dict = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    """
    Permet à l'utilisateur connecté de changer son propre mot de passe.
    Utilisé notamment pour le changement obligatoire après un premier login
    avec le compte admin par défaut ou un compte créé par un administrateur.
    """
    user = db.query(User).filter(User.id == identity.get("user_id")).first()
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")

    if not bcrypt.checkpw(payload.current_password.encode("utf-8"), user.password.encode("utf-8")):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")

    user.password = bcrypt.hashpw(payload.new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user.must_change_password = False
    db.commit()

    return {"message": "Mot de passe mis à jour"}