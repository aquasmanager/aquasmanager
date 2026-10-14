"""
transfer_certificate.py (routes)

Certificats de cession de boutures (côté cédant, connecté) et profil du
cédant. La signature de l'acquéreur passe par routes/public_certificate.py.
"""

import secrets
from datetime import datetime, timedelta
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from middleware.auth import FRAG_ROLES, min_role_required
from services.license import require_feature
from middleware.database import get_db
from pro.models.transfer_certificate import SaleLocation, TransferCertificate, TransferCertificateItem
from pro.schemas.transfer_certificate import (
    CertificateCreate,
    CertificateRead,
    CertificateSummary,
    CertificateUpdate,
    OfflineSale,
    SaleLocationRead,
    SaleLocationWrite,
    SellerProfileRead,
    SellerProfileUpdate,
)
from pro.services.certificate_pdf import render_certificate
from pro.services.transfer_reports import (
    build_report,
    certificates_zip,
    export_csv,
    registry_pdf,
    select_certificates,
    yearly_summary,
    zip_filename,
)
from services.privacy import anonymize_certificate, effective_notice, retention_cutoff
from services.frags import (
    DEFAULT_LEGAL_MENTION,
    SIGN_LINK_DAYS,
    create_certificate,
    get_seller_profile,
    clean_location_name,
    find_location,
    release_frags,
    resolve_location,
    seller_is_complete,
    seller_snapshot,
    sign_certificate,
)

# Bourse : réservée à une licence qui l'inclut
router = APIRouter(
    prefix="/transfer-certificates",
    tags=["transfer certificates"],
    dependencies=[Depends(require_feature("bourse")), Depends(min_role_required("consult"))],
)
seller_router = APIRouter(prefix="/seller-profile", tags=["transfer certificates"], dependencies=[Depends(require_feature("bourse"))])
location_router = APIRouter(
    prefix="/sale-locations", tags=["transfer certificates"], dependencies=[Depends(require_feature("bourse")), Depends(min_role_required("consult"))]
)
EXTRA_ROUTERS = (seller_router, location_router)


def _summary(certificate: TransferCertificate) -> dict:
    return {
        "id": certificate.id,
        "number": certificate.number,
        "status": certificate.status,
        "transfer_date": certificate.transfer_date,
        "buyer_name": certificate.buyer_name,
        "total_price": certificate.total_price,
        "item_count": len(certificate.items),
        "total_quantity": certificate.total_quantity,
        "location_id": certificate.location_id,
        "location_name": certificate.location_name,
        "created_at": certificate.created_at,
        "signed_at": certificate.signed_at,
        "token_expires_at": certificate.token_expires_at,
        "anonymized_at": certificate.anonymized_at,
    }


def _full(certificate: TransferCertificate) -> dict:
    return {
        **_summary(certificate),
        "notes": certificate.notes,
        "seller": certificate.seller,
        "legal_mention": certificate.legal_mention,
        "privacy_notice": certificate.privacy_notice,
        "buyer": certificate.buyer,
        "items": certificate.items,
        "sign_token": certificate.sign_token,
    }


def _get_or_404(db: Session, certificate_id: int) -> TransferCertificate:
    certificate = db.get(TransferCertificate, certificate_id)
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificat non trouvé")
    return certificate


@router.get("/", response_model=List[CertificateSummary])
def list_certificates(
    location_id: Optional[int] = Query(None, description="Lieu de vente ; 0 = certificats sans lieu"),
    db: Session = Depends(get_db),
):
    query = db.query(TransferCertificate)
    if location_id == 0:
        query = query.filter(TransferCertificate.location_id.is_(None))
    elif location_id is not None:
        query = query.filter(TransferCertificate.location_id == location_id)
    certificates = query.order_by(TransferCertificate.transfer_date.desc(), TransferCertificate.id.desc()).all()
    return [_summary(c) for c in certificates]


@router.get("/report")
def report(
    location_id: Optional[int] = Query(None, description="Lieu ; 0 = sans lieu"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Bilan des cessions signées : montant, boutures par espèce, stock restant."""
    return build_report(db, select_certificates(db, location_id, date_from, date_to))


@router.get("/yearly")
def yearly(db: Session = Depends(get_db)):
    """Cessions signées par année : nombre, boutures, montant, lieux et acquéreurs distincts."""
    return yearly_summary(db)


@router.get("/export.csv")
def export(
    location_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    content = export_csv(select_certificates(db, location_id, date_from, date_to))
    return Response(
        content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="cessions.csv"'},
    )


@router.get("/export.zip")
def export_zip(
    location_id: Optional[int] = Query(None, description="Lieu ; 0 = sans lieu"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    include_drafts: bool = Query(False, description="Inclure les certificats en attente de signature"),
    db: Session = Depends(get_db),
):
    """Tous les certificats (PDF, rangés par lieu) et le tableau CSV, en une archive."""
    certificates = select_certificates(db, location_id, date_from, date_to, signed_only=not include_drafts)
    if not certificates:
        raise HTTPException(status_code=404, detail="Aucun certificat à télécharger pour ces critères.")
    return Response(
        certificates_zip(certificates),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename(certificates, location_id, date_from, date_to)}"'},
    )


@router.get("/registry.pdf")
def registry(year: int = Query(..., ge=2000, le=2100), db: Session = Depends(get_db)):
    certificates = select_certificates(db, None, date(year, 1, 1), date(year, 12, 31), signed_only=True)
    return Response(
        registry_pdf(certificates, year, seller_snapshot(get_seller_profile(db))),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="registre-cessions-{year}.pdf"'},
    )


@router.get("/{certificate_id}", response_model=CertificateRead)
def get_certificate(certificate_id: int, db: Session = Depends(get_db)):
    return _full(_get_or_404(db, certificate_id))


@router.post(
    "/",
    response_model=CertificateRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user", also=FRAG_ROLES))],
)
def create(certificate_in: CertificateCreate, db: Session = Depends(get_db)):
    certificate = create_certificate(
        db,
        [(item.frag_id, item.quantity, item.price) for item in certificate_in.items],
        certificate_in.transfer_date,
        certificate_in.notes,
        resolve_location(db, certificate_in.location_id, certificate_in.location_name),
    )
    return _full(certificate)


@router.post(
    "/offline",
    response_model=CertificateRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user", also=FRAG_ROLES))],
)
def create_offline_sale(sale: OfflineSale, db: Session = Depends(get_db)):
    """Vente signée sans réseau (bourse) : certificat créé puis signé, à la date réelle de signature."""
    certificate = create_certificate(
        db,
        [(item.frag_id, item.quantity, item.price) for item in sale.items],
        sale.transfer_date,
        sale.notes,
        resolve_location(db, sale.location_id, sale.location_name),
        allow_shortfall=True,
    )
    # Heure envoyée par le téléphone (souvent en UTC) ramenée à l'heure du serveur, comme les autres signatures
    signed_at = sale.signed_at.astimezone().replace(tzinfo=None) if sale.signed_at.tzinfo else sale.signed_at
    sign_certificate(db, certificate, sale.buyer.model_dump(), sale.signature, signed_at)
    db.refresh(certificate)
    return _full(certificate)


@router.patch(
    "/{certificate_id}",
    response_model=CertificateRead,
    dependencies=[Depends(min_role_required("user", also=FRAG_ROLES))],
)
def update_certificate(certificate_id: int, update: CertificateUpdate, db: Session = Depends(get_db)):
    """Lieu de vente : modifiable avant signature ; après, seulement s'il n'était pas renseigné."""
    certificate = _get_or_404(db, certificate_id)
    fields = update.model_fields_set
    if fields & {"location_id", "location_name"}:
        if certificate.status == "signed" and certificate.location_id is not None:
            raise HTTPException(status_code=409, detail="Certificat signé : son lieu de vente ne peut plus être changé.")
        location = resolve_location(db, update.location_id, update.location_name)
        certificate.location_id = location.id if location else None
    db.commit()
    db.refresh(certificate)
    return _full(certificate)


@router.post(
    "/{certificate_id}/renew-link",
    response_model=CertificateRead,
    dependencies=[Depends(min_role_required("user", also=FRAG_ROLES))],
)
def renew_link(certificate_id: int, db: Session = Depends(get_db)):
    """Nouveau lien de signature (l'ancien ne fonctionne plus)."""
    certificate = _get_or_404(db, certificate_id)
    if certificate.status != "draft":
        raise HTTPException(status_code=409, detail="Certificat déjà signé.")
    certificate.sign_token = secrets.token_urlsafe(32)
    certificate.token_expires_at = datetime.now() + timedelta(days=SIGN_LINK_DAYS)
    db.commit()
    db.refresh(certificate)
    return _full(certificate)


@router.post(
    "/{certificate_id}/anonymize",
    response_model=CertificateRead,
    dependencies=[Depends(min_role_required("manager"))],
)
def anonymize(certificate_id: int, db: Session = Depends(get_db)):
    """Demande d'effacement : identité, coordonnées et signature de l'acquéreur effacées
    (définitif) ; le certificat garde les spécimens, les dates et le lieu."""
    certificate = _get_or_404(db, certificate_id)
    if certificate.anonymized_at is not None:
        raise HTTPException(status_code=409, detail="Ce certificat est déjà anonymisé.")
    anonymize_certificate(db, certificate)
    db.commit()
    db.refresh(certificate)
    return _full(certificate)


@router.get("/{certificate_id}/pdf")
def download_pdf(certificate_id: int, db: Session = Depends(get_db)):
    certificate = _get_or_404(db, certificate_id)
    return Response(
        render_certificate(certificate),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificat-{certificate.number}.pdf"'},
    )


@router.delete(
    "/{certificate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("user", also=FRAG_ROLES))],
)
def delete_certificate(certificate_id: int, db: Session = Depends(get_db)):
    """Seul un certificat non signé peut être supprimé (ses boutures redeviennent disponibles)."""
    certificate = _get_or_404(db, certificate_id)
    if certificate.status != "draft":
        raise HTTPException(status_code=409, detail="Un certificat signé ne peut pas être supprimé.")
    release_frags(db, certificate)
    db.commit()


def _profile_read(profile) -> dict:
    return {
        **{f: getattr(profile, f) for f in SellerProfileRead.model_fields if f not in ("complete", "effective_privacy_notice")},
        "effective_privacy_notice": effective_notice(profile),
        # Texte vide : celui repris sur les certificats (texte par défaut)
        "legal_mention": profile.legal_mention or DEFAULT_LEGAL_MENTION,
        "complete": seller_is_complete(profile),
    }


@seller_router.get("/", response_model=SellerProfileRead, dependencies=[Depends(min_role_required("consult"))])
def get_profile(db: Session = Depends(get_db)):
    return _profile_read(get_seller_profile(db))


@seller_router.get("/retention-preview", dependencies=[Depends(min_role_required("consult"))])
def retention_preview(years: int = Query(..., ge=0, le=30), db: Session = Depends(get_db)):
    """Certificats dont l'acquéreur serait anonymisé avec cette durée de conservation."""
    cutoff = retention_cutoff(years)
    if cutoff is None:
        return {"cutoff": None, "count": 0}
    count = (
        db.query(func.count(TransferCertificate.id))
        .filter(TransferCertificate.transfer_date < cutoff, TransferCertificate.anonymized_at.is_(None))
        .scalar()
    )
    return {"cutoff": cutoff, "count": count}


@seller_router.put("/", response_model=SellerProfileRead, dependencies=[Depends(min_role_required("manager"))])
def update_profile(profile_in: SellerProfileUpdate, db: Session = Depends(get_db)):
    profile = get_seller_profile(db)
    for field, value in profile_in.model_dump(exclude={"signature"}).items():
        setattr(profile, field, value.strip() if isinstance(value, str) else value)
    if profile_in.signature is not None:
        profile.signature = profile_in.signature or None
    db.commit()
    db.refresh(profile)
    return _profile_read(profile)


@location_router.get("/", response_model=List[SaleLocationRead])
def list_locations(db: Session = Depends(get_db)):
    """Lieux de vente avec le bilan de leurs cessions (nombre, boutures, montant, dernière date)."""
    stats = {
        location_id: (count, last_date)
        for location_id, count, last_date in db.query(
            TransferCertificate.location_id, func.count(TransferCertificate.id), func.max(TransferCertificate.transfer_date)
        )
        .group_by(TransferCertificate.location_id)
        .all()
    }
    totals = {
        location_id: (quantity, amount)
        for location_id, quantity, amount in db.query(
            TransferCertificate.location_id,
            func.sum(TransferCertificateItem.quantity),
            func.sum(TransferCertificateItem.quantity * TransferCertificateItem.price),
        )
        .join(TransferCertificateItem, TransferCertificateItem.certificate_id == TransferCertificate.id)
        .group_by(TransferCertificate.location_id)
        .all()
    }
    result = []
    for location in db.query(SaleLocation).order_by(SaleLocation.name).all():
        count, last_date = stats.get(location.id, (0, None))
        quantity, amount = totals.get(location.id, (0, None))
        result.append(
            {
                "id": location.id,
                "name": location.name,
                "certificate_count": count,
                "total_quantity": int(quantity or 0),
                "total_price": round(amount, 2) if amount is not None else None,
                "last_transfer_date": last_date,
            }
        )
    return result


@location_router.post(
    "/",
    response_model=SaleLocationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("user", also=FRAG_ROLES))],
)
def create_location(location_in: SaleLocationWrite, db: Session = Depends(get_db)):
    name = clean_location_name(location_in.name)
    if not name:
        raise HTTPException(status_code=400, detail="Nom du lieu requis.")
    if find_location(db, name):
        raise HTTPException(status_code=409, detail="Ce lieu existe déjà.")
    location = SaleLocation(name=name)
    db.add(location)
    db.commit()
    db.refresh(location)
    return {"id": location.id, "name": location.name}


@location_router.patch(
    "/{location_id}",
    response_model=SaleLocationRead,
    dependencies=[Depends(min_role_required("user", also=FRAG_ROLES))],
)
def rename_location(location_id: int, location_in: SaleLocationWrite, db: Session = Depends(get_db)):
    location = db.get(SaleLocation, location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Lieu non trouvé")
    name = clean_location_name(location_in.name)
    existing = find_location(db, name)
    if not name or (existing and existing.id != location.id):
        raise HTTPException(status_code=409, detail="Un autre lieu porte déjà ce nom.")
    location.name = name
    db.commit()
    return {"id": location.id, "name": location.name}


@location_router.delete(
    "/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("manager"))],
)
def delete_location(location_id: int, db: Session = Depends(get_db)):
    location = db.get(SaleLocation, location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Lieu non trouvé")
    if db.query(TransferCertificate).filter(TransferCertificate.location_id == location_id).count():
        raise HTTPException(status_code=409, detail="Des certificats utilisent ce lieu : il ne peut pas être supprimé.")
    db.delete(location)
    db.commit()
