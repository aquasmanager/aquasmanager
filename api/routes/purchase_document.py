"""
purchase_document.py (routes)

Documents d'achat (factures, certificats reçus, permis CITES) liés aux
spécimens, pour justifier leur origine en cas de contrôle. Les fichiers ne
sont servis qu'aux comptes connectés (contrairement aux photos).
"""

import csv
import io
from datetime import datetime
import os
import re
import shutil
import unicodedata
import uuid
import zipfile
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from middleware.auth import min_role_required
from middleware.database import get_db
from models.aquarium import Aquarium
from models.coral import Coral
from models.fish import Fish
from models.invertebrate import Invertebrate
from models.purchase_document import PurchaseDocument, PurchaseDocumentFile, PurchaseDocumentLink
from services.cites_links import join_numbers, link_corals_to_document, normalize, split_numbers
import json

from models.coral import Coral as CoralModel
from models.species import CoralSpecies
from schemas.purchase_document import (
    CitesSuggestion,
    DocumentFileRead,
    DocumentLinkIn,
    LinkableSpecimen,
    PurchaseDocumentCreate,
    PurchaseDocumentRead,
    PurchaseDocumentUpdate,
)

router = APIRouter(
    prefix="/purchase-documents", tags=["purchase documents"], dependencies=[Depends(min_role_required("consult"))]
)
WRITE = [Depends(min_role_required("user"))]

STORAGE_ROOT = os.path.join("uploads", "purchase_documents")
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_FILES_PER_DOCUMENT = 20
# Extension -> type servi, et signature attendue en tête de fichier
ALLOWED = {
    ".pdf": ("application/pdf", (b"%PDF",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".png": ("image/png", (b"\x89PNG",)),
    ".webp": ("image/webp", (b"RIFF",)),
    ".heic": ("image/heic", (b"ftyp",)),
    ".heif": ("image/heif", (b"ftyp",)),
}
MODELS = {"corals": Coral, "invertebrates": Invertebrate, "fish": Fish}


# --- Lecture ---


def _labels(db: Session, links: list[PurchaseDocumentLink]) -> dict[tuple[str, int], tuple[str, int]]:
    """(type, id) -> (libellé, id de l'aquarium) pour les spécimens encore présents."""
    found: dict[tuple[str, int], tuple[str, int]] = {}
    for entity_type, model in MODELS.items():
        ids = [link.entity_id for link in links if link.entity_type == entity_type]
        if not ids:
            continue
        rows = (
            db.query(model.id, model.name, Aquarium.name, Aquarium.id)
            .join(Aquarium, Aquarium.id == model.aquarium_id)
            .filter(model.id.in_(ids))
        )
        for entity_id, name, aquarium_name, aquarium_id in rows:
            found[(entity_type, entity_id)] = (f"{name} · {aquarium_name}", aquarium_id)
    return found


def _species_map(document: PurchaseDocument) -> dict[str, int]:
    try:
        data = json.loads(document.cites_species or "{}")
    except ValueError:
        return {}
    return {k: int(v) for k, v in data.items() if str(v).isdigit()} if isinstance(data, dict) else {}


def _cites_entries(document: PurchaseDocument, names: dict[int, str]) -> list[dict]:
    species = _species_map(document)
    entries = []
    for number in split_numbers(document.cites_number):
        species_id = species.get(normalize(number))
        entries.append({"number": number, "coral_species_id": species_id, "coral_species_name": names.get(species_id)})
    return entries


def _read(documents: list[PurchaseDocument], db: Session) -> list[dict]:
    labels = _labels(db, [link for d in documents for link in d.links])
    species_ids = {i for d in documents for i in _species_map(d).values()}
    names = (
        {s.id: s.common_name for s in db.query(CoralSpecies).filter(CoralSpecies.id.in_(species_ids))}
        if species_ids else {}
    )
    result = []
    for d in documents:
        result.append(
            {
                "id": d.id,
                "title": d.title,
                "supplier": d.supplier,
                "purchase_date": d.purchase_date,
                "reference": d.reference,
                "cites_number": d.cites_number,
                "cites_numbers": split_numbers(d.cites_number),
                "cites_entries": _cites_entries(d, names),
                "notes": d.notes,
                "created_at": d.created_at,
                "files": d.files,
                "links": [
                    {
                        "entity_type": link.entity_type,
                        "entity_id": link.entity_id,
                        "label": labels.get((link.entity_type, link.entity_id), (None, None))[0],
                        "aquarium_id": labels.get((link.entity_type, link.entity_id), (None, None))[1],
                    }
                    for link in d.links
                ],
            }
        )
    return result


def _query(db: Session, entity_type: Optional[str], entity_ids: Optional[List[int]], q: Optional[str]):
    query = db.query(PurchaseDocument)
    if entity_type and entity_ids:
        query = query.join(PurchaseDocumentLink).filter(
            PurchaseDocumentLink.entity_type == entity_type, PurchaseDocumentLink.entity_id.in_(entity_ids)
        )
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            PurchaseDocument.title.ilike(like)
            | PurchaseDocument.supplier.ilike(like)
            | PurchaseDocument.reference.ilike(like)
            | PurchaseDocument.cites_number.ilike(like)
        )
    return query.distinct().order_by(PurchaseDocument.purchase_date.desc(), PurchaseDocument.id.desc()).all()


@router.get("/", response_model=List[PurchaseDocumentRead])
def list_documents(
    entity_type: Optional[str] = Query(None, pattern="^(corals|invertebrates|fish)$"),
    entity_id: Optional[List[int]] = Query(None, description="Un ou plusieurs spécimens"),
    q: Optional[str] = Query(None, max_length=100),
    db: Session = Depends(get_db),
):
    return _read(_query(db, entity_type, entity_id, q), db)


@router.get("/cites-suggestions", response_model=List[CitesSuggestion])
def cites_suggestions(coral_species_id: int = Query(..., gt=0), db: Session = Depends(get_db)):
    """Numéros CITES des documents d'achat associés à cette espèce de corail (les plus
    récents d'abord), avec les coraux qui les portent déjà."""
    used: dict[str, list[str]] = {}
    for coral in db.query(CoralModel).filter(CoralModel.cites != ""):
        used.setdefault(normalize(coral.cites), []).append(coral.name)
    rows = []
    documents = db.query(PurchaseDocument).filter(PurchaseDocument.cites_species.contains(str(coral_species_id)))
    for document in documents:
        species = _species_map(document)
        for number in split_numbers(document.cites_number):
            if species.get(normalize(number)) == coral_species_id:
                rows.append({
                    "number": number, "document_id": document.id, "document_title": document.title,
                    "supplier": document.supplier, "purchase_date": document.purchase_date,
                    "used_by": used.get(normalize(number), []),
                })
    return sorted(rows, key=lambda r: (bool(r["used_by"]), -(r["purchase_date"].toordinal() if r["purchase_date"] else 0)))


@router.get("/specimens", response_model=List[LinkableSpecimen])
def linkable_specimens(db: Session = Depends(get_db)):
    """Spécimens auxquels lier un document (coraux, invertébrés, poissons de tous les bacs)."""
    rows = []
    for entity_type, model in MODELS.items():
        for item, aquarium in db.query(model, Aquarium).join(Aquarium, Aquarium.id == model.aquarium_id):
            rows.append(
                {
                    "entity_type": entity_type,
                    "entity_id": item.id,
                    "name": item.name,
                    "scientific_name": item.scientific_name or "",
                    "cites": getattr(item, "cites", "") or "",
                    "aquarium_id": aquarium.id,
                    "aquarium_name": aquarium.name,
                }
            )
    return sorted(rows, key=lambda r: (r["entity_type"], r["name"].lower()))


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9.]+", "-", ascii_text).strip("-").lower()[:60] or "document"


@router.get("/export.zip")
def export_zip(
    entity_type: Optional[str] = Query(None, pattern="^(corals|invertebrates|fish)$"),
    entity_id: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
):
    """Tous les documents (ou ceux des spécimens demandés) : un dossier par document et un index CSV."""
    documents = _query(db, entity_type, entity_id, None)
    if not documents:
        raise HTTPException(status_code=404, detail="Aucun document à télécharger.")
    labels = _labels(db, [link for d in documents for link in d.links])
    index = io.StringIO()
    writer = csv.writer(index, delimiter=";")
    writer.writerow(["Dossier", "Titre", "Fournisseur", "Date", "Référence", "N° CITES", "Spécimens liés", "Fichiers", "Notes"])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for d in documents:
            folder = f"{d.purchase_date or 'sans-date'}_{_slug(d.title)}_{d.id}"
            names = []
            for f in d.files:
                path = _file_path(d.id, f.filename)
                if os.path.exists(path):
                    name = f"{f.id}_{_slug(f.original_name)}"
                    archive.write(path, f"{folder}/{name}")
                    names.append(name)
            specimens = ", ".join(labels.get((link.entity_type, link.entity_id), ("(supprimé)", None))[0] for link in d.links)
            writer.writerow([folder, d.title, d.supplier, d.purchase_date or "", d.reference, "; ".join(split_numbers(d.cites_number)),
                             specimens, " | ".join(names), (d.notes or "").replace("\n", " ")])
        archive.writestr("index.csv", "﻿" + index.getvalue())
    return Response(
        buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="documents-achat.zip"'},
    )


def _get_or_404(db: Session, document_id: int) -> PurchaseDocument:
    document = db.get(PurchaseDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document non trouvé")
    return document


@router.get("/{document_id}", response_model=PurchaseDocumentRead)
def get_document(document_id: int, db: Session = Depends(get_db)):
    return _read([_get_or_404(db, document_id)], db)[0]


def _file_path(document_id: int, filename: str) -> str:
    return os.path.join(STORAGE_ROOT, str(document_id), filename)


@router.get("/{document_id}/files/{file_id}")
def download_file(document_id: int, file_id: int, download: bool = False, db: Session = Depends(get_db)):
    file = db.get(PurchaseDocumentFile, file_id)
    if file is None or file.document_id != document_id:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")
    path = _file_path(document_id, file.filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Fichier absent du serveur")
    return FileResponse(
        path,
        media_type=file.content_type,
        filename=file.original_name,
        content_disposition_type="attachment" if download else "inline",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"},
    )


# --- Écriture ---


def _set_links(db: Session, document: PurchaseDocument, links: list[DocumentLinkIn]) -> None:
    wanted = {(link.entity_type, link.entity_id) for link in links}
    for entity_type in {t for t, _ in wanted}:
        ids = {i for t, i in wanted if t == entity_type}
        model = MODELS[entity_type]
        existing = {row[0] for row in db.query(model.id).filter(model.id.in_(ids))}
        if ids - existing:
            raise HTTPException(status_code=400, detail="Un des spécimens à lier n'existe pas.")
    current = {(link.entity_type, link.entity_id): link for link in document.links}
    for key, link in current.items():
        if key not in wanted:
            document.links.remove(link)
    for entity_type, entity_id in sorted(wanted - current.keys()):
        document.links.append(PurchaseDocumentLink(entity_type=entity_type, entity_id=entity_id))


def _apply_entries(document: PurchaseDocument, entries) -> None:
    """Numéros CITES et espèce de chacun (cites_entries)."""
    document.cites_number = join_numbers(e.number for e in entries)
    document.cites_species = json.dumps(
        {normalize(e.number): e.coral_species_id for e in entries if e.coral_species_id}
    )


def _cites(numbers: Optional[list[str]], text: Optional[str]) -> Optional[str]:
    """Numéros CITES envoyés en liste (cites_numbers) ou en texte (cites_number)."""
    if numbers is not None:
        return join_numbers(numbers)
    if text is not None:
        return join_numbers([text])
    return None


@router.post("/", response_model=PurchaseDocumentRead, status_code=status.HTTP_201_CREATED, dependencies=WRITE)
def create_document(payload: PurchaseDocumentCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude={"links", "cites_numbers", "cites_number", "cites_entries"})
    document = PurchaseDocument(**{k: v.strip() if isinstance(v, str) else v for k, v in data.items()})
    if payload.cites_entries is not None:
        _apply_entries(document, payload.cites_entries)
    else:
        document.cites_number = _cites(payload.cites_numbers or None, payload.cites_number) or ""
    db.add(document)
    _set_links(db, document, payload.links)
    auto_linked = link_corals_to_document(db, document, split_numbers(document.cites_number))
    db.commit()
    db.refresh(document)
    return {**_read([document], db)[0], "auto_linked": auto_linked}


@router.patch("/{document_id}", response_model=PurchaseDocumentRead, dependencies=WRITE)
def update_document(document_id: int, payload: PurchaseDocumentUpdate, db: Session = Depends(get_db)):
    document = _get_or_404(db, document_id)
    data = payload.model_dump(exclude_unset=True)
    links = data.pop("links", None)
    entries = data.pop("cites_entries", None)
    numbers = _cites(data.pop("cites_numbers", None), data.pop("cites_number", None))
    if entries is not None:
        numbers = join_numbers(e["number"] for e in entries)
    for field, value in data.items():
        if field == "title" and not value:
            continue
        setattr(document, field, value.strip() if isinstance(value, str) else value)
    if links is not None:
        _set_links(db, document, payload.links or [])
    auto_linked = 0
    if numbers is not None:
        before = {normalize(n) for n in split_numbers(document.cites_number)}
        if entries is not None:
            _apply_entries(document, payload.cites_entries or [])
        else:
            document.cites_number = numbers
            # Espèces gardées pour les numéros toujours présents
            kept = {normalize(n) for n in split_numbers(numbers)}
            document.cites_species = json.dumps({k: v for k, v in _species_map(document).items() if k in kept})
        # Seuls les numéros ajoutés lient des coraux : un lien retiré à la main ne revient pas
        added = [n for n in split_numbers(numbers) if normalize(n) not in before]
        auto_linked = link_corals_to_document(db, document, added)
    db.commit()
    db.refresh(document)
    return {**_read([document], db)[0], "auto_linked": auto_linked}


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=WRITE)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    document = _get_or_404(db, document_id)
    folder = os.path.join(STORAGE_ROOT, str(document.id))
    db.delete(document)
    db.commit()
    shutil.rmtree(folder, ignore_errors=True)


def _checked_extension(file: UploadFile, head: bytes) -> tuple[str, str]:
    ext = os.path.splitext(os.path.basename(file.filename or ""))[1].lower()
    if ext not in ALLOWED:
        raise HTTPException(status_code=400, detail="Format non pris en charge : PDF, JPEG, PNG, WebP ou HEIC.")
    content_type, signatures = ALLOWED[ext]
    probe = head[4:12] if ext in (".heic", ".heif") else head
    if not any(probe.startswith(sig) for sig in signatures):
        raise HTTPException(status_code=400, detail=f"« {file.filename} » n'est pas un fichier {ext[1:].upper()} valide.")
    return ext, content_type


@router.post(
    "/{document_id}/files",
    response_model=List[DocumentFileRead],
    status_code=status.HTTP_201_CREATED,
    dependencies=WRITE,
)
def upload_files(document_id: int, files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    document = _get_or_404(db, document_id)
    if len(document.files) + len(files) > MAX_FILES_PER_DOCUMENT:
        raise HTTPException(status_code=400, detail=f"{MAX_FILES_PER_DOCUMENT} fichiers au plus par document.")
    folder = os.path.join(STORAGE_ROOT, str(document.id))
    os.makedirs(folder, exist_ok=True)
    added: list[PurchaseDocumentFile] = []
    written_paths: list[str] = []
    try:
        _store_files(document, files, folder, added, written_paths)
    except HTTPException:
        # Envoi refusé en cours de route : on ne garde aucun des fichiers de cet envoi
        for path in written_paths:
            if os.path.exists(path):
                os.remove(path)
        db.rollback()
        raise
    db.commit()
    return added


def _store_files(document, files, folder, added, written_paths) -> None:
    for upload in files:
        head = upload.file.read(16)
        ext, content_type = _checked_extension(upload, head)
        filename = f"{uuid.uuid4().hex}{ext}"
        path = os.path.join(folder, filename)
        written_paths.append(path)
        written = len(head)
        with open(path, "wb") as out:
            out.write(head)
            while chunk := upload.file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_FILE_BYTES:
                    out.close()
                    os.remove(path)
                    raise HTTPException(status_code=413, detail=f"« {upload.filename} » est trop lourd (20 Mo maximum).")
                out.write(chunk)
        record = PurchaseDocumentFile(
            filename=filename,
            original_name=os.path.basename(upload.filename or filename)[:200],
            content_type=content_type,
            size=written,
        )
        document.files.append(record)
        added.append(record)


MAX_SCAN_PAGES = 30


@router.post(
    "/{document_id}/scan",
    response_model=DocumentFileRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=WRITE,
)
def scan_to_pdf(
    document_id: int,
    pages: List[UploadFile] = File(...),
    name: Optional[str] = Form(None, max_length=120),
    db: Session = Depends(get_db),
):
    """Pages photographiées (facture, certificat) réunies en un seul PDF, dans l'ordre reçu."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    document = _get_or_404(db, document_id)
    if not pages or len(pages) > MAX_SCAN_PAGES:
        raise HTTPException(status_code=400, detail=f"Entre 1 et {MAX_SCAN_PAGES} pages par PDF.")
    if len(document.files) >= MAX_FILES_PER_DOCUMENT:
        raise HTTPException(status_code=400, detail=f"{MAX_FILES_PER_DOCUMENT} fichiers au plus par document.")
    images = []
    try:
        for page in pages:
            data = page.file.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                raise HTTPException(status_code=413, detail="Une page dépasse 20 Mo.")
            try:
                image = Image.open(io.BytesIO(data))
                image = ImageOps.exif_transpose(image).convert("RGB")
            except (UnidentifiedImageError, OSError):
                raise HTTPException(status_code=400, detail=f"« {page.filename} » n'est pas une image lisible.")
            images.append(image)
        buffer = io.BytesIO()
        images[0].save(buffer, format="PDF", save_all=True, append_images=images[1:], resolution=150)
    finally:
        for image in images:
            image.close()
    if buffer.tell() > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Le PDF dépasse 20 Mo : moins de pages, ou des photos plus légères.")

    folder = os.path.join(STORAGE_ROOT, str(document.id))
    os.makedirs(folder, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.pdf"
    with open(os.path.join(folder, filename), "wb") as out:
        out.write(buffer.getvalue())
    label = re.sub(r"[\\/:*?\"<>|]+", "-", (name or "").strip()) or f"scan-{datetime.now():%Y%m%d-%H%M}"
    record = PurchaseDocumentFile(
        filename=filename,
        original_name=(label if label.lower().endswith(".pdf") else f"{label}.pdf")[:200],
        content_type="application/pdf",
        size=buffer.tell(),
    )
    document.files.append(record)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{document_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=WRITE)
def delete_file(document_id: int, file_id: int, db: Session = Depends(get_db)):
    file = db.get(PurchaseDocumentFile, file_id)
    if file is None or file.document_id != document_id:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")
    path = _file_path(document_id, file.filename)
    db.delete(file)
    db.commit()
    if os.path.exists(path):
        os.remove(path)
