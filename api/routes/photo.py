"""
Photos des fiches : envoi, liste, photo principale, suppression.
"""

import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from starlette.responses import FileResponse
from middleware.auth import FRAG_ROLES, min_role_required
from models.photo import Photo, PhotoType
from schemas.photo import PhotoRead
from middleware.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/photos", tags=["Photo"])

UPLOAD_ROOT = "uploads"
# Formats d'image acceptés (jamais de SVG : il peut contenir du script)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif"}
MAX_PHOTO_BYTES = 20 * 1024 * 1024


def _safe_extension(file: UploadFile) -> str:
    """Extension d'image autorisée ; le nom envoyé par le navigateur n'est jamais réutilisé tel quel."""
    ext = os.path.splitext(os.path.basename(file.filename or ""))[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        content_type = (file.content_type or "").lower()
        guessed = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif",
                   "image/heic": ".heic", "image/heif": ".heif"}.get(content_type)
        if guessed is None:
            raise HTTPException(status_code=400, detail="Format non pris en charge : JPEG, PNG, WebP, GIF ou HEIC.")
        ext = guessed
    return ext


def photo_writer(min_role: str):
    """Niveau minimal requis ; le rôle bourse n'agit que sur les photos de boutures."""
    checker = min_role_required(min_role, also=FRAG_ROLES)

    def check(entity_type: PhotoType, identity: dict = Depends(checker)):
        if identity.get("role") in FRAG_ROLES and entity_type != PhotoType.frags:
            raise HTTPException(status_code=403, detail="Ce compte ne gère que les photos des boutures.")
        return identity

    return check


def _taken_at(filepath: str, declared: Optional[datetime]) -> Optional[datetime]:
    """Date de prise de vue : EXIF de l'image si elle l'a gardé, sinon la date du fichier
    d'origine envoyée par l'appli (les photos sont recompressées avant l'envoi)."""
    taken = None
    try:
        from PIL import Image

        with Image.open(filepath) as image:
            raw = image.getexif().get_ifd(0x8769).get(0x9003) or image.getexif().get(0x0132)
        if raw:
            taken = datetime.strptime(str(raw).strip()[:19], "%Y:%m:%d %H:%M:%S")
    except Exception:
        taken = None
    if taken is None and declared is not None:
        taken = declared.astimezone(timezone.utc).replace(tzinfo=None) if declared.tzinfo else declared
    # Date plausible seulement (appareil mal réglé, fichier copié...)
    if taken is None or taken.year < 2000 or taken > datetime.now():
        return None
    return taken


@router.post(
    "/{entity_type}/{entity_id}",
    response_model=PhotoRead,
    dependencies=[Depends(photo_writer("user"))],
)
def create_photo(
    entity_type: PhotoType,
    entity_id: int,
    file: UploadFile = File(...),
    taken_at: Optional[datetime] = Form(default=None),
    db: Session = Depends(get_db),
):
    # Définit le répertoire d'upload et le crée s'il n'existe pas
    folder = os.path.join(UPLOAD_ROOT, entity_type.value, str(entity_id))
    os.makedirs(folder, exist_ok=True)

    # Nom généré (jamais celui du navigateur : pas de « ../ » possible) et taille limitée
    unique_name = f"{uuid.uuid4().hex}{_safe_extension(file)}"
    filepath = os.path.join(folder, unique_name)
    written = 0
    with open(filepath, "wb") as f:
        while chunk := file.file.read(1024 * 1024):
            written += len(chunk)
            if written > MAX_PHOTO_BYTES:
                f.close()
                os.remove(filepath)
                raise HTTPException(status_code=413, detail="Photo trop lourde (20 Mo maximum).")
            f.write(chunk)

    # Vérifie si l'entité a déjà une photo principale
    has_main = (
        db.query(Photo)
        .filter(Photo.entity_type == entity_type, Photo.entity_id == entity_id, Photo.is_main.is_(True))
        .first()
    )

    # Insère les informations dans la base
    photo = Photo(
        filename=unique_name, entity_type=entity_type, entity_id=entity_id, is_main=False if has_main else True
    )
    taken = _taken_at(filepath, taken_at)
    if taken is not None:
        photo.created_at = taken
    db.add(photo)
    db.commit()
    db.refresh(photo)

    return photo


@router.get("/{entity_type}/{entity_id}", response_model=list[PhotoRead])
def list_photos(entity_type: PhotoType, entity_id: int, db: Session = Depends(get_db)):
    return db.query(Photo).filter(Photo.entity_type == entity_type, Photo.entity_id == entity_id).all()


@router.get("/{entity_type}/{entity_id}/main")
def get_photo_main(entity_type: PhotoType, entity_id: int, db: Session = Depends(get_db)):
    photo = (
        db.query(Photo)
        .filter(Photo.entity_type == entity_type, Photo.entity_id == entity_id, Photo.is_main.is_(True))
        .first()
    )

    if not photo:
        path = os.path.join("default", "photo", "image_default.jpg")
    else:
        path = os.path.join(UPLOAD_ROOT, entity_type.value, str(entity_id), str(photo.filename))

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Fichier image non trouvé")

    return FileResponse(path)


@router.get("/{entity_type}/{entity_id}/{photo_id}/file")
def get_photo_file(entity_type: PhotoType, entity_id: int, photo_id: int, db: Session = Depends(get_db)):
    """
    Sert le fichier d'une photo précise (pas forcément la principale) —
    utilisé pour les vignettes de la galerie. Public comme get_photo_main :
    une balise <img> ne peut pas envoyer de header Authorization.
    """
    photo = (
        db.query(Photo)
        .filter(Photo.id == photo_id, Photo.entity_type == entity_type, Photo.entity_id == entity_id)
        .first()
    )
    if not photo:
        raise HTTPException(status_code=404, detail="Photo non trouvée")

    path = os.path.join(UPLOAD_ROOT, entity_type.value, str(entity_id), str(photo.filename))
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Fichier image non trouvé")

    return FileResponse(path)


@router.patch(
    "/{entity_type}/{entity_id}/{photo_id}/main",
    response_model=PhotoRead,
    dependencies=[Depends(photo_writer("user"))],
)
def set_main_photo(entity_type: PhotoType, entity_id: int, photo_id: int, db: Session = Depends(get_db)):
    photo = (
        db.query(Photo)
        .filter(Photo.id == photo_id, Photo.entity_type == entity_type, Photo.entity_id == entity_id)
        .first()
    )
    if not photo:
        raise HTTPException(status_code=404, detail="Photo non trouvée")

    db.query(Photo).filter(
        Photo.entity_type == entity_type,
        Photo.entity_id == entity_id,
        Photo.id != photo_id,
    ).update({"is_main": False})

    photo.is_main = True
    db.commit()
    db.refresh(photo)
    return photo


@router.delete(
    "/{entity_type}/{entity_id}/{photo_id}",
    dependencies=[Depends(photo_writer("manager"))],
)
def delete_photo(entity_type: PhotoType, entity_id: int, photo_id: int, db: Session = Depends(get_db)):
    photo = db.query(Photo).filter(Photo.id == photo_id).first()

    if not photo:
        raise HTTPException(status_code=404, detail="Photo non trouvée")

    path = os.path.join(UPLOAD_ROOT, entity_type.value, str(entity_id), photo.filename)

    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as err:
        logger.error(f"Erreur lors de la suppression du fichier: {err}")

    was_main = photo.is_main
    db.delete(photo)
    db.commit()

    # Si on supprime la photo principale, promeut une des photos restantes
    # (sinon plus aucune photo n'est "principale" et get_photo_main retombe
    # sur l'image par défaut même s'il reste des photos valides).
    if was_main:
        replacement = (
            db.query(Photo)
            .filter(Photo.entity_type == entity_type, Photo.entity_id == entity_id)
            .order_by(Photo.created_at.desc())
            .first()
        )
        if replacement:
            replacement.is_main = True
            db.commit()

    return {"detail": "Photo supprimée"}


@router.delete(
    "/{entity_type}/{entity_id}",
    dependencies=[Depends(photo_writer("manager"))],
)
def delete_photo_entity(entity_type: PhotoType, entity_id: int, db: Session = Depends(get_db)):
    photos = db.query(Photo).filter(Photo.entity_type == entity_type, Photo.entity_id == entity_id).all()

    if not photos:
        return {"detail": "Aucune photo à supprimer"}

    path = os.path.join(UPLOAD_ROOT, entity_type.value, str(entity_id))

    try:
        if os.path.exists(path):
            shutil.rmtree(path)
    except Exception as err:
        logger.error(f"Erreur lors de la suppression des fichiers: {err}")

    for photo in photos:
        db.delete(photo)
    db.commit()

    return {"detail": "Photos supprimées"}