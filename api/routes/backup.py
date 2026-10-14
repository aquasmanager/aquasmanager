"""
backup.py (routes)

Sauvegardes : réglages (automatique, contenu, destination), liste des
sauvegardes locales et externes, création, export, import, restauration.
Tout est réservé aux administrateurs : une sauvegarde contient toutes les
données (hashs de mot de passe compris) et une restauration les remplace.
"""

import logging
import os
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask
from starlette.responses import FileResponse, JSONResponse

from middleware.auth import min_role_required
from middleware.database import get_db
from schemas.backup import BackupCreate, BackupInfo, BackupSettingsBase, BackupSettingsRead, DestinationTest
from services.backup import (
    PARTS,
    _describe,
    build_export,
    check_external_dir,
    register_external_dir,
    create_backup,
    delete_backup,
    get_backup_path,
    get_backup_settings,
    import_backup,
    list_backups,
    next_run,
    restore_backup,
    settings_parts,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backup", tags=["Backup"], dependencies=[Depends(min_role_required("admin"))])


def _settings_read(conf) -> dict:
    data = {field: getattr(conf, field) for field in BackupSettingsRead.model_fields if hasattr(conf, field)}
    data["next_run_at"] = next_run(conf)
    if conf.external_path:
        try:
            check_external_dir(conf.external_path)
            data["external_ok"] = True
        except HTTPException as exc:
            data["external_ok"], data["external_error"] = False, exc.detail
    return data


@router.get("/", response_model=List[BackupInfo])
def get_backups():
    return list_backups()


@router.get("/settings", response_model=BackupSettingsRead)
def read_settings(db: Session = Depends(get_db)):
    return _settings_read(get_backup_settings(db))


@router.put("/settings", response_model=BackupSettingsRead)
def update_settings(payload: BackupSettingsBase, db: Session = Depends(get_db)):
    if payload.destination == "external" or payload.external_path:
        register_external_dir(payload.external_path or "")
    conf = get_backup_settings(db)
    for field, value in payload.model_dump().items():
        setattr(conf, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(conf)
    return _settings_read(conf)


@router.post("/test-destination")
def test_destination(payload: DestinationTest):
    folder = check_external_dir(payload.path, require_marker=False)
    free = shutil.disk_usage(folder).free
    return {"ok": True, "message": f"Dossier accessible en écriture ({free / 1024**3:.1f} Go libres)."}


@router.post("/create", response_model=BackupInfo, status_code=201)
def create(payload: BackupCreate, db: Session = Depends(get_db)):
    """Sauvegarde rangée sur le serveur (sans téléchargement)."""
    location = payload.location or get_backup_settings(db).destination
    path = create_backup(label="manual", parts=payload.parts, location=location)
    return _describe(path, location)


@router.post("/export")
def export_backup(payload: BackupCreate | None = None, db: Session = Depends(get_db)):
    """Archive téléchargée directement, non conservée sur le serveur."""
    parts = payload.parts if payload and payload.parts is not None else settings_parts(get_backup_settings(db))
    path = build_export(list(parts))
    return FileResponse(
        path=str(path),
        filename=path.name.replace("_export_", "_"),
        media_type="application/zip",
        background=BackgroundTask(lambda: path.unlink(missing_ok=True)),
    )


@router.post("/import", response_model=BackupInfo, status_code=201)
async def import_archive(file: UploadFile = File(...)):
    """Archive envoyée : vérifiée puis ajoutée à la liste ; la restauration se lance à part."""
    # Nom temporaire généré : le nom du fichier envoyé n'entre pas dans le chemin
    tmp_path = Path(tempfile.gettempdir()) / f"aquasmanager_import_{threading.get_ident()}_{uuid.uuid4().hex}.zip"
    try:
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        return import_backup(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


@router.get("/{location}/{filename}")
def download_backup(location: str, filename: str):
    path = get_backup_path(filename, location)
    return FileResponse(path=str(path), filename=path.name, media_type="application/zip")


@router.delete("/{location}/{filename}", status_code=204)
def remove_backup(location: str, filename: str):
    delete_backup(filename, location)


def _restart_process():
    # Laisse partir la réponse, puis redémarre : sous Docker / k8s le conteneur
    # est relancé et les migrations sont rejouées sur la base restaurée.
    time.sleep(1)
    logger.warning("Redémarrage du process après restauration...")
    os._exit(0)


@router.post("/{location}/{filename}/restore")
def restore(location: str, filename: str):
    parts = restore_backup(get_backup_path(filename, location))
    restored = ", ".join(["la base", *(PARTS[p].lower() for p in parts)])
    return JSONResponse(
        content={"message": f"Restauration faite ({restored}). Le service redémarre (quelques secondes)."},
        background=BackgroundTask(_restart_process),
    )
