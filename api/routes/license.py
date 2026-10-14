"""
license.py (routes)

Licence de l'installation : état (fonctionnalités ouvertes), et clé collée
par un administrateur.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from middleware.auth import min_role_required
from middleware.database import get_db
from services import license as lic

router = APIRouter(prefix="/license", tags=["license"])


class LicenseRead(BaseModel):
    valid: bool
    source: Optional[str]
    features: list[str]
    # Fonctionnalités soumises à licence (nom → description)
    paid_features: dict[str, str]
    license_id: Optional[str]
    client: Optional[str]
    issued: Optional[str]
    expires: Optional[str]
    error: Optional[str]
    instance_id: str


class LicenseKey(BaseModel):
    key: str = Field(min_length=10, max_length=4000)


def _read(status: lic.LicenseStatus) -> LicenseRead:
    return LicenseRead(
        valid=status.valid,
        source=status.source,
        features=status.features,
        paid_features=lic.PAID_FEATURES,
        license_id=status.license_id,
        client=status.client,
        issued=status.issued,
        expires=status.expires,
        error=status.error,
        instance_id=status.instance_id,
    )


@router.get("/", response_model=LicenseRead, dependencies=[Depends(min_role_required("consult"))])
def get_license(db: Session = Depends(get_db)):
    return _read(lic.compute_status(db))


@router.put("/", response_model=LicenseRead, dependencies=[Depends(min_role_required("admin"))])
def set_license(payload: LicenseKey, db: Session = Depends(get_db)):
    row = lic.license_row(db)
    try:
        lic.decode_key(payload.key, row.instance_id)
    except lic.LicenseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    row.license_key = payload.key.strip()
    row.updated_at = datetime.now()
    db.commit()
    lic.invalidate_cache()
    return _read(lic.compute_status(db))


@router.delete("/", response_model=LicenseRead, dependencies=[Depends(min_role_required("admin"))])
def remove_license(db: Session = Depends(get_db)):
    row = lic.license_row(db)
    row.license_key = None
    row.updated_at = datetime.now()
    db.commit()
    lic.invalidate_cache()
    return _read(lic.compute_status(db))
