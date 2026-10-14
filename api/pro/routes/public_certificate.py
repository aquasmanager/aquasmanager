"""
public_certificate.py (routes)

Page de signature de l'acquéreur : accessible SANS compte, par le lien à
jeton du certificat (valable SIGN_LINK_DAYS jours, puis SIGNED_LINK_DAYS
jours pour télécharger le PDF signé). N'expose ni le jeton ni les signatures.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from middleware.database import get_db
from pro.models.transfer_certificate import TransferCertificate
from pro.schemas.transfer_certificate import CertificateSign, PublicCertificateRead
from pro.services.certificate_pdf import render_certificate
from services.frags import get_by_token, sign_certificate
from services.license import require_feature

# Signature par l'acquéreur : bourse, réservée à une licence qui l'inclut
router = APIRouter(prefix="/public/certificates", tags=["public"], dependencies=[Depends(require_feature("bourse"))])


def _public(certificate: TransferCertificate) -> dict:
    return {
        "number": certificate.number,
        "status": certificate.status,
        "transfer_date": certificate.transfer_date,
        "location_name": certificate.location_name,
        "notes": certificate.notes,
        "seller": certificate.seller,
        "legal_mention": certificate.legal_mention,
        "privacy_notice": certificate.privacy_notice,
        "buyer": certificate.buyer,
        "items": certificate.items,
        "total_price": certificate.total_price,
        "total_quantity": certificate.total_quantity,
        "signed_at": certificate.signed_at,
    }


@router.get("/{token}", response_model=PublicCertificateRead)
def get_public_certificate(token: str, db: Session = Depends(get_db)):
    return _public(get_by_token(db, token))


@router.post("/{token}/sign", response_model=PublicCertificateRead)
def sign(token: str, payload: CertificateSign, db: Session = Depends(get_db)):
    certificate = get_by_token(db, token)
    sign_certificate(db, certificate, payload.buyer.model_dump(), payload.signature)
    db.refresh(certificate)
    return _public(certificate)


@router.get("/{token}/pdf")
def download_signed_pdf(token: str, db: Session = Depends(get_db)):
    certificate = get_by_token(db, token)
    if certificate.status != "signed":
        raise HTTPException(status_code=409, detail="Le certificat n'est pas encore signé.")
    return Response(
        render_certificate(certificate),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificat-{certificate.number}.pdf"'},
    )
