"""
Paramètres d'eau : relevés, tendances, cibles par défaut et analyses ICP.
"""

import logging
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session
from starlette.responses import FileResponse

from middleware.auth import CARE_ROLES, min_role_required
from middleware.database import get_db
from models.water_parameter import WaterParameter, WaterParameterReading, IcpImportBatch
from schemas.water_parameter import (
    WaterParameterCreate,
    WaterParameterRead,
    WaterParameterUpdate,
    WaterParameterReadingCreate,
    WaterParameterReadingUpdate,
    WaterParameterReadingRead,
    WaterParameterReadingBatchCreate,
    IcpImportRow,
    IcpImportBatchCreate,
    IcpImportBatchRead,
    IcpBatchReadingRead,
    TargetDefaultRead,
    ApplyDefaultTargetsResult,
)
from services.parameter_trends import trends_for_aquarium
from services.icp_import import parse_icp_report
from services.water_parameter_defaults import TARGET_DEFAULTS, default_target_for, full_name_for
from utils.safe_path import safe_join

logger = logging.getLogger(__name__)

ICP_PDF_DIR = os.path.join("uploads", "icp")
ICP_PDF_MAX_BYTES = 20 * 1024 * 1024


def _icp_pdf_path(batch_id: int) -> str:
    return safe_join(ICP_PDF_DIR, f"{batch_id}.pdf")

router = APIRouter(
    prefix="/water-parameters", tags=["Water Parameters"], dependencies=[Depends(min_role_required("consult"))]
)


@router.get("/", response_model=List[WaterParameterRead])
def list_water_parameters(aquarium_id: int = Query(...), db: Session = Depends(get_db)):
    return (
        db.query(WaterParameter)
        .filter(WaterParameter.aquarium_id == aquarium_id)
        .order_by(WaterParameter.name)
        .all()
    )


@router.get("/trends")
def list_trends(aquarium_id: int = Query(...), db: Session = Depends(get_db)) -> List[dict]:
    """Tendance de chaque paramètre (relevés des 3 dernières semaines) et date estimée de sortie de cible."""
    return trends_for_aquarium(db, aquarium_id)


@router.get("/target-defaults", response_model=List[TargetDefaultRead])
def list_target_defaults():
    return [
        {"name": name, "full_name": full_name_for(name), **default._asdict()}
        for name, default in TARGET_DEFAULTS.items()
    ]


@router.post(
    "/apply-default-targets",
    response_model=ApplyDefaultTargetsResult,
    dependencies=[Depends(min_role_required("user"))],
)
def apply_default_targets(aquarium_id: int = Query(...), db: Session = Depends(get_db)):
    """Remplace la cible des paramètres connus de la table (même unité) par la valeur par défaut."""
    params = db.query(WaterParameter).filter(WaterParameter.aquarium_id == aquarium_id).order_by(WaterParameter.name).all()
    updated = []
    for param in params:
        default = default_target_for(param.name, param.unit)
        if default is None or (param.target_min, param.target_max) == (default.target_min, default.target_max):
            continue
        param.target_min = default.target_min
        param.target_max = default.target_max
        if not param.unit:
            param.unit = default.unit
        updated.append(param.name)
    db.commit()
    return {"updated": updated, "parameters": params}


@router.post(
    "/icp-import/parse",
    response_model=List[IcpImportRow],
    dependencies=[Depends(min_role_required("user"))],
)
async def parse_icp_import(lab: str = Query(...), file: UploadFile = File(...)):
    """
    Extrait les valeurs d'un rapport d'analyse ICP (PDF) sans rien écrire en
    base : le résultat est une proposition à relire/corriger côté client
    avant un import réel via les routes existantes (paramètres + relevés).
    """
    if file.content_type != "application/pdf" and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Seuls les fichiers PDF sont supportés pour le moment.")

    content = await file.read()
    return parse_icp_report(lab, content)


@router.get("/icp-batches/", response_model=List[IcpImportBatchRead])
def list_icp_batches(aquarium_id: int = Query(...), db: Session = Depends(get_db)):
    return (
        db.query(IcpImportBatch)
        .filter(IcpImportBatch.aquarium_id == aquarium_id)
        .order_by(IcpImportBatch.sample_date)
        .all()
    )


@router.post(
    "/icp-batches/",
    response_model=IcpImportBatchRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user"))],
)
def create_icp_batch(batch_in: IcpImportBatchCreate, db: Session = Depends(get_db)):
    batch = IcpImportBatch(**batch_in.model_dump())
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/icp-batches/{batch_id}/readings", response_model=List[IcpBatchReadingRead])
def list_icp_batch_readings(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(IcpImportBatch).filter(IcpImportBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Test ICP non trouvé")

    rows = (
        db.query(WaterParameterReading, WaterParameter)
        .join(WaterParameter, WaterParameter.id == WaterParameterReading.water_parameter_id)
        .filter(WaterParameterReading.icp_batch_id == batch_id)
        .all()
    )
    return [
        {
            "water_parameter_id": param.id,
            "name": param.name,
            "unit": param.unit,
            "value": reading.value,
        }
        for reading, param in rows
    ]


@router.post(
    "/icp-batches/{batch_id}/pdf",
    response_model=IcpImportBatchRead,
    dependencies=[Depends(min_role_required("user"))],
)
async def upload_icp_batch_pdf(batch_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    batch = db.query(IcpImportBatch).filter(IcpImportBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Test ICP non trouvé")

    content = await file.read(ICP_PDF_MAX_BYTES + 1)
    if len(content) > ICP_PDF_MAX_BYTES:
        raise HTTPException(status_code=413, detail="PDF trop volumineux (20 Mo maximum).")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Le fichier n'est pas un PDF valide.")

    os.makedirs(ICP_PDF_DIR, exist_ok=True)
    with open(_icp_pdf_path(batch_id), "wb") as f:
        f.write(content)

    batch.pdf_filename = os.path.basename(file.filename or f"icp_{batch_id}.pdf")[:255]

    db.commit()
    db.refresh(batch)
    return batch


@router.get("/icp-batches/{batch_id}/pdf")
def get_icp_batch_pdf(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(IcpImportBatch).filter(IcpImportBatch.id == batch_id).first()
    path = _icp_pdf_path(batch_id)
    if not batch or not batch.pdf_filename or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Aucun PDF pour ce test ICP")
    return FileResponse(
        path, media_type="application/pdf", filename=batch.pdf_filename, content_disposition_type="inline"
    )


@router.delete(
    "/icp-batches/{batch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("manager"))],
)
def delete_icp_batch(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(IcpImportBatch).filter(IcpImportBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Test ICP non trouvé")

    db.delete(batch)
    db.commit()

    if os.path.exists(_icp_pdf_path(batch_id)):
        os.remove(_icp_pdf_path(batch_id))


@router.post(
    "/readings/batch",
    response_model=List[WaterParameterReadingRead],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user", also=CARE_ROLES))],
)
def create_water_parameter_readings_batch(batch_in: WaterParameterReadingBatchCreate, db: Session = Depends(get_db)):
    """Enregistre plusieurs relevés d'un coup (ex. KH, Ca et Mg après une série de tests)."""
    ids = [item.water_parameter_id for item in batch_in.values]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=400, detail="Un même paramètre est saisi deux fois.")
    params = {
        p.id: p
        for p in db.query(WaterParameter).filter(
            WaterParameter.id.in_(ids), WaterParameter.aquarium_id == batch_in.aquarium_id
        )
    }
    missing = [str(i) for i in ids if i not in params]
    if missing:
        raise HTTPException(status_code=400, detail=f"Paramètre(s) inconnu(s) pour cet aquarium : {', '.join(missing)}")

    readings = []
    for item in batch_in.values:
        reading = WaterParameterReading(water_parameter_id=item.water_parameter_id, value=item.value, note=batch_in.note)
        if batch_in.timestamp is not None:
            reading.timestamp = batch_in.timestamp
        db.add(reading)
        readings.append(reading)
    db.commit()
    for reading in readings:
        db.refresh(reading)
    return readings


@router.post(
    "/",
    response_model=WaterParameterRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user"))],
)
def create_water_parameter(param_in: WaterParameterCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(WaterParameter)
        .filter(WaterParameter.aquarium_id == param_in.aquarium_id, WaterParameter.name == param_in.name)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Ce paramètre existe déjà pour cet aquarium")

    param = WaterParameter(**param_in.model_dump())
    # Cible par défaut seulement si l'appelant n'en a fourni aucune (un null explicite est respecté)
    if not {"target_min", "target_max"} & param_in.model_fields_set:
        default = default_target_for(param.name, param.unit)
        if default:
            param.target_min, param.target_max = default.target_min, default.target_max
            param.unit = param.unit or default.unit
    db.add(param)
    db.commit()
    db.refresh(param)
    return param


@router.patch(
    "/{param_id}",
    response_model=WaterParameterRead,
    dependencies=[Depends(min_role_required("user"))],
)
def update_water_parameter(param_id: int, update_data: WaterParameterUpdate, db: Session = Depends(get_db)):
    param = db.query(WaterParameter).filter(WaterParameter.id == param_id).first()
    if not param:
        raise HTTPException(status_code=404, detail="Paramètre non trouvé")

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(param, field, value)

    db.commit()
    db.refresh(param)
    return param


@router.delete(
    "/{param_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("manager"))],
)
def delete_water_parameter(param_id: int, db: Session = Depends(get_db)):
    param = db.query(WaterParameter).filter(WaterParameter.id == param_id).first()
    if not param:
        raise HTTPException(status_code=404, detail="Paramètre non trouvé")

    db.delete(param)
    db.commit()


@router.get("/{param_id}/readings", response_model=List[WaterParameterReadingRead])
def list_water_parameter_readings(
    param_id: int,
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Limite le nombre de relevés (les plus récents)"),
    db: Session = Depends(get_db),
):
    param = db.query(WaterParameter).filter(WaterParameter.id == param_id).first()
    if not param:
        raise HTTPException(status_code=404, detail="Paramètre non trouvé")

    query = db.query(WaterParameterReading).filter(WaterParameterReading.water_parameter_id == param_id)
    if limit is not None:
        return list(reversed(query.order_by(WaterParameterReading.timestamp.desc()).limit(limit).all()))
    return query.order_by(WaterParameterReading.timestamp).all()


@router.post(
    "/{param_id}/readings",
    response_model=WaterParameterReadingRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user", also=CARE_ROLES))],
)
def create_water_parameter_reading(
    param_id: int, reading_in: WaterParameterReadingCreate, db: Session = Depends(get_db)
):
    param = db.query(WaterParameter).filter(WaterParameter.id == param_id).first()
    if not param:
        raise HTTPException(status_code=404, detail="Paramètre non trouvé")

    data = reading_in.model_dump(exclude_unset=True)
    data.pop("timestamp", None)
    reading = WaterParameterReading(water_parameter_id=param_id, **data)
    if reading_in.timestamp is not None:
        reading.timestamp = reading_in.timestamp
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return reading


@router.patch(
    "/{param_id}/readings/{reading_id}",
    response_model=WaterParameterReadingRead,
    dependencies=[Depends(min_role_required("user"))],
)
def update_water_parameter_reading(
    param_id: int, reading_id: int, update_data: WaterParameterReadingUpdate, db: Session = Depends(get_db)
):
    reading = (
        db.query(WaterParameterReading)
        .filter(WaterParameterReading.id == reading_id, WaterParameterReading.water_parameter_id == param_id)
        .first()
    )
    if not reading:
        raise HTTPException(status_code=404, detail="Relevé non trouvé")

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(reading, field, value)

    db.commit()
    db.refresh(reading)
    return reading


@router.delete(
    "/{param_id}/readings/{reading_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("manager"))],
)
def delete_water_parameter_reading(param_id: int, reading_id: int, db: Session = Depends(get_db)):
    reading = (
        db.query(WaterParameterReading)
        .filter(WaterParameterReading.id == reading_id, WaterParameterReading.water_parameter_id == param_id)
        .first()
    )
    if not reading:
        raise HTTPException(status_code=404, detail="Relevé non trouvé")

    db.delete(reading)
    db.commit()


# Déclarée en dernier : les routes statiques (/target-defaults, /icp-batches/...) passent avant.
@router.get("/{param_id}", response_model=WaterParameterRead)
def get_water_parameter(param_id: int, db: Session = Depends(get_db)):
    param = db.query(WaterParameter).filter(WaterParameter.id == param_id).first()
    if not param:
        raise HTTPException(status_code=404, detail="Paramètre non trouvé")
    return param
