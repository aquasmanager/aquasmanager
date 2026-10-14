"""
services/backup.py

Sauvegardes AquasManager : une archive zip contenant toujours la base
SQLite, et au choix les photos, les rapports ICP, les documents d'achat et
les certificats de cession (PDF générés, pour consultation).

Deux emplacements :
- « local » : base/backups/, sur le même volume que la base ;
- « external » : un dossier monté par l'hôte (partage NFS, disque USB...),
  choisi dans les réglages. L'application ne monte rien elle-même.

Chaque archive porte un manifest.json (date, type, contenu) : la
restauration ne remplace que les parties présentes dans l'archive.

Conservation :
- automatiques : les N plus récentes (réglage keep_count) ;
- « avant restauration » : backup_retention_days jours ;
- manuelles et importées : gardées jusqu'à leur suppression.
"""

import json
import logging
import os
import re
import shutil
import sqlite3
import tempfile
import time
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from middleware.database import SessionLocal, db_conf, engine
from models.backup_settings import BackupSettings
from settings import settings as app_settings

logger = logging.getLogger(__name__)

# Tables attendues dans un export valide : sert juste à détecter qu'on ne
# tente pas de restaurer un fichier qui n'est pas un export AquasManager.
REQUIRED_TABLES = {"users", "controllers", "aquariums"}

DB_ENTRY_NAME = "aquarium.db"
UPLOADS_ENTRY_NAME = "uploads"
MANIFEST_NAME = "manifest.json"
CERTIFICATES_ENTRY_NAME = "certificats"

# Parties optionnelles d'une sauvegarde (la base est toujours incluse)
PARTS = {
    "photos": "Photos",
    "icp": "Rapports ICP",
    "documents": "Documents d'achat",
    "certificates": "Certificats de cession (PDF)",
}
# Sous-dossiers de uploads/ propres à une partie ; tout le reste = photos
PART_DIRS = {"icp": "icp", "documents": "purchase_documents"}
# Parties restaurables (les certificats PDF se régénèrent depuis la base)
RESTORABLE_PARTS = ("photos", "icp", "documents")
# Archives antérieures au manifeste : base + tout le dossier uploads
LEGACY_PARTS = ["photos", "icp", "documents"]

LABELS = {
    "auto": "Automatique",
    "manual": "Manuelle",
    "imported": "Importée",
    "before_restore": "Avant restauration",
    "export": "Export",
}
# Type non gourmand : « auto_abcdef » = type « auto » + suffixe aléatoire
FILENAME_RE = re.compile(r"^aquarium_(\d{8}_\d{6})_([a-z_]+?)(?:_[0-9a-f]{6})?\.zip$")


def _ensure_sqlite():
    if db_conf.type != "sqlite":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Sauvegarde non disponible pour ce type de base (MySQL) pour le moment.",
        )


def _db_path() -> Path:
    return Path(db_conf.sqlite_path).resolve()


def _uploads_dir() -> Path:
    # Même chemin relatif « uploads » que celui des photos et documents
    return Path("uploads").resolve()


# --- Réglages ---------------------------------------------------------------


def get_backup_settings(db) -> BackupSettings:
    conf = db.get(BackupSettings, 1)
    if conf is None:
        conf = BackupSettings(
            id=1,
            enabled=app_settings.backup_auto_default,
            external_path=app_settings.backup_external_path or None,
            destination="external" if app_settings.backup_external_path else "local",
        )
        db.add(conf)
        db.commit()
        db.refresh(conf)
    return conf


def settings_parts(conf: BackupSettings) -> list[str]:
    return [p for p in PARTS if getattr(conf, f"include_{p}")]


# --- Emplacements -----------------------------------------------------------


def _local_dir() -> Path:
    path = _db_path().parent / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


# Fichier témoin déposé dans la destination externe à son enregistrement : s'il
# manque, le partage n'est pas monté (dossier vide sur le disque local)
DESTINATION_MARKER = ".aquasmanager-backups"


def check_external_dir(path: Optional[str], require_marker: bool = True) -> Path:
    """Dossier externe utilisable : existe, accepte l'écriture, et c'est bien la
    destination configurée (fichier témoin présent)."""
    if not path or not path.strip():
        raise HTTPException(status_code=400, detail="Indique le dossier externe (partage NFS monté, disque...).")
    folder = Path(path.strip())
    if not folder.is_absolute():
        raise HTTPException(status_code=400, detail="Le dossier externe doit être un chemin absolu (ex : /backups-nfs).")
    if not folder.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Le dossier {folder} n'existe pas dans le conteneur : le partage est-il bien monté ?",
        )
    probe = folder / f".aquasmanager-test-{uuid.uuid4().hex[:8]}"
    try:
        probe.write_bytes(b"ok")
        probe.unlink()
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Écriture impossible dans {folder} : {exc.strerror or exc}.") from exc
    if require_marker and not (folder / DESTINATION_MARKER).exists():
        raise HTTPException(
            status_code=400,
            detail=f"{folder} ne contient pas le fichier témoin d'AquasManager : le partage n'est sans doute pas monté.",
        )
    return folder


def register_external_dir(path: str) -> Path:
    """Enregistrement de la destination : vérifiée puis marquée du fichier témoin."""
    folder = check_external_dir(path, require_marker=False)
    marker = folder / DESTINATION_MARKER
    if not marker.exists():
        marker.write_text("Destination des sauvegardes AquasManager (ne pas supprimer).\n", encoding="utf-8")
    return folder


def _location_dir(location: str, conf: Optional[BackupSettings] = None) -> Path:
    if location == "local":
        return _local_dir()
    if location == "external":
        if conf is None:
            with SessionLocal() as db:
                external = get_backup_settings(db).external_path
        else:
            external = conf.external_path
        return check_external_dir(external)
    raise HTTPException(status_code=400, detail="Emplacement inconnu.")


# --- Création ---------------------------------------------------------------


def _add_uploads(zf: zipfile.ZipFile, parts: Iterable[str]) -> None:
    uploads = _uploads_dir()
    if not uploads.exists():
        return
    parts = set(parts)
    special = set(PART_DIRS.values())
    for child in uploads.iterdir():
        if not child.is_dir():
            continue
        part = next((p for p, d in PART_DIRS.items() if d == child.name), "photos" if child.name not in special else None)
        if part not in parts:
            continue
        for file_path in child.rglob("*"):
            if file_path.is_file():
                zf.write(file_path, arcname=str(Path(UPLOADS_ENTRY_NAME) / file_path.relative_to(uploads)))


def _add_certificates(zf: zipfile.ZipFile) -> int:
    """PDF des certificats signés, rangés par lieu (consultation hors application)."""
    from pro.models.transfer_certificate import TransferCertificate
    from pro.services.certificate_pdf import render_certificate
    from pro.services.transfer_reports import _slug

    count = 0
    with SessionLocal() as db:
        for certificate in db.query(TransferCertificate).filter(TransferCertificate.status == "signed"):
            folder = _slug(certificate.location_name) if certificate.location_name else "sans-lieu"
            zf.writestr(f"{CERTIFICATES_ENTRY_NAME}/{folder}/certificat-{certificate.number}.pdf", render_certificate(certificate))
            count += 1
    return count


def _build_archive(target: Path, label: str, parts: list[str]) -> None:
    _ensure_sqlite()
    source_path = _db_path()
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Fichier de base introuvable")
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Instantané cohérent via l'API backup() de sqlite3 (écritures en cours comprises)
        tmp_db_path = Path(tmp_dir) / DB_ENTRY_NAME
        source_conn = sqlite3.connect(str(source_path))
        dest_conn = sqlite3.connect(str(tmp_db_path))
        try:
            source_conn.backup(dest_conn)
        finally:
            dest_conn.close()
            source_conn.close()

        partial = target.with_suffix(".zip.part")
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(tmp_db_path, arcname=DB_ENTRY_NAME)
            _add_uploads(zf, parts)
            certificates = _add_certificates(zf) if "certificates" in parts else 0
            zf.writestr(MANIFEST_NAME, json.dumps({
                "application": "AquasManager",
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "label": label,
                "parts": ["database", *parts],
                "certificates": certificates,
            }, ensure_ascii=False, indent=1))
        # Archive complète seulement : pas de fichier à moitié écrit sur un partage réseau
        os.replace(partial, target)


def _archive_name(label: str) -> str:
    return f"aquarium_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{label}_{uuid.uuid4().hex[:6]}.zip"


def create_backup(label: str = "manual", parts: Optional[list[str]] = None, location: Optional[str] = None) -> Path:
    """Crée et range une sauvegarde. parts / location : ceux des réglages par défaut."""
    with SessionLocal() as db:
        conf = get_backup_settings(db)
        parts = [p for p in (parts if parts is not None else settings_parts(conf)) if p in PARTS]
        location = location or conf.destination
        folder = _location_dir(location, conf)
    target = folder / _archive_name(label)
    _build_archive(target, label, parts)
    logger.info("Sauvegarde créée : %s (%s)", target, ", ".join(["base", *parts]))
    return target


def build_export(parts: list[str]) -> Path:
    """Archive temporaire à télécharger (non rangée dans la liste)."""
    target = Path(tempfile.gettempdir()) / _archive_name("export")
    _build_archive(target, "export", [p for p in parts if p in PARTS])
    return target


# --- Liste ------------------------------------------------------------------


def _read_manifest(path: Path) -> dict:
    try:
        with zipfile.ZipFile(path) as zf:
            if MANIFEST_NAME in zf.namelist():
                return json.loads(zf.read(MANIFEST_NAME))
    except (zipfile.BadZipFile, json.JSONDecodeError, OSError):
        return {"invalid": True}
    return {}


def _describe(path: Path, location: str) -> dict:
    stat = path.stat()
    match = FILENAME_RE.match(path.name)
    manifest = _read_manifest(path)
    # Le nom du fichier fait foi (une archive importée garde le manifeste d'origine)
    label = match.group(2) if match else manifest.get("label", "manual")
    parts = [p for p in manifest.get("parts", ["database", *LEGACY_PARTS]) if p != "database"]
    return {
        "filename": path.name,
        "location": location,
        "size_bytes": stat.st_size,
        "created_at": datetime.fromtimestamp(stat.st_mtime),
        "label": label,
        "label_text": LABELS.get(label, label),
        "parts": parts,
        "legacy": not manifest,
        "valid": not manifest.get("invalid", False),
    }


def list_backups() -> list[dict]:
    _ensure_sqlite()
    rows = [_describe(f, "local") for f in _local_dir().glob("*.zip")]
    with SessionLocal() as db:
        external = get_backup_settings(db).external_path
    if external:
        try:
            rows += [_describe(f, "external") for f in check_external_dir(external).glob("*.zip")]
        except HTTPException:
            pass  # partage indisponible : l'interface l'indique via les réglages
    return sorted(rows, key=lambda r: r["created_at"], reverse=True)


def get_backup_path(filename: str, location: str = "local") -> Path:
    _ensure_sqlite()
    # Pas de chemin dans le nom (../, absolu) : uniquement un fichier de l'emplacement
    safe_name = Path(filename).name
    path = _location_dir(location) / safe_name
    if safe_name != filename or not safe_name.endswith(".zip") or not path.is_file():
        raise HTTPException(status_code=404, detail="Sauvegarde introuvable")
    return path


def delete_backup(filename: str, location: str) -> None:
    get_backup_path(filename, location).unlink()


# --- Conservation -----------------------------------------------------------


def prune_auto_backups(keep: int, location: str) -> int:
    folder = _location_dir(location)
    autos = sorted(
        (f for f in folder.glob("*.zip") if (m := FILENAME_RE.match(f.name)) and m.group(2) == "auto"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    removed = 0
    for old in autos[max(keep, 1):]:
        old.unlink(missing_ok=True)
        removed += 1
    return removed


def purge_old_backups(retention_days: int) -> int:
    """Sauvegardes « avant restauration » (et anciens exports) plus vieilles que retention_days."""
    _ensure_sqlite()
    cutoff = time.time() - retention_days * 86400
    deleted = 0
    for f in _local_dir().glob("*.zip"):
        match = FILENAME_RE.match(f.name)
        if match and match.group(2) in ("before_restore", "export") and f.stat().st_mtime < cutoff:
            f.unlink()
            deleted += 1
    if deleted:
        logger.info("Purge des sauvegardes : %d fichier(s) de plus de %d jours supprimé(s).", deleted, retention_days)
    return deleted


# --- Import et restauration ---------------------------------------------------


def _validate_sqlite_file(path: Path):
    try:
        conn = sqlite3.connect(str(path))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
    except sqlite3.DatabaseError as exc:
        raise HTTPException(status_code=400, detail=f"Fichier invalide : ce n'est pas une base SQLite lisible ({exc}).")
    missing = REQUIRED_TABLES - tables
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Fichier invalide : tables manquantes ({', '.join(sorted(missing))}). "
            "Ce n'est probablement pas une sauvegarde AquasManager.",
        )


def _validate_archive(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as zf:
            if DB_ENTRY_NAME not in zf.namelist():
                raise HTTPException(status_code=400, detail=f"Archive invalide : {DB_ENTRY_NAME} introuvable.")
            with tempfile.TemporaryDirectory() as tmp:
                zf.extract(DB_ENTRY_NAME, tmp)
                _validate_sqlite_file(Path(tmp) / DB_ENTRY_NAME)
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Fichier invalide : ce n'est pas une archive zip valide.") from exc


def import_backup(upload_path: Path) -> dict:
    """Archive envoyée : vérifiée puis rangée dans la liste (restauration à part)."""
    _ensure_sqlite()
    _validate_archive(upload_path)
    target = _local_dir() / _archive_name("imported")
    shutil.copyfile(upload_path, target)
    return _describe(target, "local")


def restore_backup(archive_path: Path) -> list[str]:
    """
    Remplace la base, et les parties présentes dans l'archive (photos,
    rapports ICP, documents d'achat) ; les autres restent telles quelles.
    Une sauvegarde complète de l'état actuel est faite juste avant.
    Le moteur SQLAlchemy est « disposé », puis l'appelant redémarre le
    process pour rejouer les migrations sur la base restaurée.
    """
    _ensure_sqlite()
    _validate_archive(archive_path)
    manifest = _read_manifest(archive_path)
    parts = [p for p in manifest.get("parts", ["database", *LEGACY_PARTS]) if p in RESTORABLE_PARTS]

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        with zipfile.ZipFile(archive_path) as zf:
            members = [m for m in zf.namelist() if m == DB_ENTRY_NAME or m.startswith(f"{UPLOADS_ENTRY_NAME}/")]
            zf.extractall(tmp, members=members)

        # Filet de sécurité : état actuel complet, dans le dossier local
        create_backup(label="before_restore", parts=list(RESTORABLE_PARTS), location="local")

        shutil.copyfile(tmp / DB_ENTRY_NAME, _db_path())
        engine.dispose()

        live = _uploads_dir()
        live.mkdir(parents=True, exist_ok=True)
        extracted = tmp / UPLOADS_ENTRY_NAME
        special = set(PART_DIRS.values())
        for part in parts:
            if part == "photos":
                targets = [d.name for d in live.iterdir() if d.is_dir() and d.name not in special]
                sources = [d.name for d in extracted.iterdir() if d.is_dir() and d.name not in special] if extracted.exists() else []
            else:
                targets = sources = [PART_DIRS[part]]
            for name in set(targets):
                shutil.rmtree(live / name, ignore_errors=True)
            for name in set(sources):
                if (extracted / name).exists():
                    shutil.copytree(extracted / name, live / name, dirs_exist_ok=True)

    logger.warning("Sauvegarde %s restaurée (base%s).", archive_path.name, "".join(f", {p}" for p in parts))
    return parts


# --- Sauvegarde automatique ---------------------------------------------------


def _last_slot(conf: BackupSettings, now_local: datetime) -> datetime:
    slot = now_local.replace(hour=conf.hour, minute=0, second=0, microsecond=0)
    if conf.frequency == "weekly":
        slot -= timedelta(days=(slot.weekday() - conf.weekday) % 7)
    if slot > now_local:
        slot -= timedelta(days=7 if conf.frequency == "weekly" else 1)
    return slot


def next_run(conf: BackupSettings, now_local: Optional[datetime] = None) -> Optional[datetime]:
    if not conf.enabled:
        return None
    now_local = now_local or datetime.now(ZoneInfo(app_settings.timezone))
    return _last_slot(conf, now_local) + timedelta(days=7 if conf.frequency == "weekly" else 1)


def run_scheduled_backup_if_due(now_local: Optional[datetime] = None) -> Optional[Path]:
    """Appelée chaque minute : lance la sauvegarde automatique si son créneau est passé."""
    if db_conf.type != "sqlite":
        return None
    tz = ZoneInfo(app_settings.timezone)
    now_local = now_local or datetime.now(tz)
    with SessionLocal() as db:
        conf = get_backup_settings(db)
        if not conf.enabled:
            return None
        slot = _last_slot(conf, now_local)
        last = conf.last_run_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz) if conf.last_run_at else None
        if last is not None and last >= slot:
            return None
        parts, destination, keep = settings_parts(conf), conf.destination, conf.keep_count

    status_, message, path = "ok", "", None
    try:
        path = create_backup("auto", parts, destination)
        prune_auto_backups(keep, destination)
        message = f"{path.name} ({'dossier externe' if destination == 'external' else 'local'})"
    except Exception as exc:  # noqa: BLE001 — on tente le dossier local avant d'abandonner
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        logger.error("Sauvegarde automatique impossible (%s) : %s", destination, detail)
        status_ = "error"
        message = f"Échec : {detail}"
        if destination == "external":
            try:
                path = create_backup("auto", parts, "local")
                prune_auto_backups(keep, "local")
                message += f" — sauvegarde faite en local ({path.name})"
            except Exception as fallback_exc:  # noqa: BLE001
                logger.exception("Sauvegarde locale de secours impossible")
                message += f" — et en local : {fallback_exc}"
        try:
            from services import notify

            notify.dispatch_alert("[AquasManager] Sauvegarde automatique en échec", message)
        except Exception:  # noqa: BLE001
            logger.exception("Notification d'échec de sauvegarde impossible")

    with SessionLocal() as db:
        conf = get_backup_settings(db)
        # Heure de ce passage (UTC naïf, comme le reste de la base), pas l'heure
        # réelle : le créneau reste cohérent même si le calcul part d'un instant donné
        conf.last_run_at = now_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        conf.last_status = status_
        conf.last_message = message[:1000]
        db.commit()
    return path
