"""
services/privacy.py

Données personnelles des acquéreurs (RGPD) : mention d'information montrée à
la signature, durée de conservation, anonymisation (automatique à échéance
ou à la demande). L'anonymisation garde ce qui sert à la traçabilité des
spécimens (numéro, date, lieu, boutures, CITES) et efface l'identité, les
coordonnées et la signature de l'acquéreur.
"""

import logging
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from pro.models.showcase import ShowcaseReservation
from pro.models.transfer_certificate import SellerProfile, TransferCertificate

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_YEARS = 5
ANONYMOUS_BUYER = {"first_name": "Acquéreur", "last_name": "anonymisé"}


def _duration(years: int) -> str:
    if years <= 0:
        return "la durée nécessaire à la traçabilité des spécimens"
    return f"{years} an{'s' if years > 1 else ''} après la cession"


def default_privacy_notice(years: int) -> str:
    return (
        "Les informations que vous renseignez (nom, adresse, coordonnées, signature) servent uniquement "
        "à établir ce certificat de cession et à assurer la traçabilité des spécimens cédés. Elles sont "
        f"conservées par le cédant pendant {_duration(years)}, puis anonymisées. Elles ne sont transmises "
        "à personne, sauf à une autorité de contrôle qui en ferait la demande. Vous pouvez demander à y "
        "accéder, à les rectifier ou à les faire effacer en contactant le cédant."
    )


def effective_notice(profile: SellerProfile) -> str:
    return (profile.privacy_notice or "").strip() or default_privacy_notice(profile.buyer_retention_years)


def retention_cutoff(years: int, today: Optional[date] = None) -> Optional[date]:
    """Cessions antérieures à cette date : données de l'acquéreur à anonymiser (None = jamais)."""
    if years <= 0:
        return None
    today = today or date.today()
    try:
        return today.replace(year=today.year - years)
    except ValueError:  # 29 février
        return today.replace(year=today.year - years, day=28)


def anonymize_certificate(db: Session, certificate: TransferCertificate) -> None:
    if certificate.buyer is not None or certificate.buyer_signature:
        certificate.buyer = dict(ANONYMOUS_BUYER) if certificate.buyer is not None else None
    certificate.buyer_signature = None
    # Les notes reprennent parfois le nom ou le contact (réservation de la vitrine)
    certificate.notes = None
    certificate.anonymized_at = datetime.now()
    for reservation in db.query(ShowcaseReservation).filter(ShowcaseReservation.certificate_id == certificate.id):
        _anonymize_reservation(reservation)


def _anonymize_reservation(reservation: ShowcaseReservation) -> None:
    reservation.name = "Anonymisé"
    reservation.contact = "—"
    reservation.message = None


def anonymize_expired(db: Session, profile: SellerProfile, today: Optional[date] = None) -> int:
    cutoff = retention_cutoff(profile.buyer_retention_years, today)
    if cutoff is None:
        return 0
    certificates = (
        db.query(TransferCertificate)
        .filter(TransferCertificate.transfer_date < cutoff, TransferCertificate.anonymized_at.is_(None))
        .all()
    )
    for certificate in certificates:
        anonymize_certificate(db, certificate)
    # Réservations de la vitrine jamais concrétisées, aussi anciennes
    limit = datetime.combine(cutoff, datetime.min.time())
    for reservation in db.query(ShowcaseReservation).filter(
        ShowcaseReservation.created_at < limit, ShowcaseReservation.name != "Anonymisé"
    ):
        _anonymize_reservation(reservation)
    db.commit()
    if certificates:
        logger.info("RGPD : %d certificat(s) anonymisé(s) (cessions antérieures au %s)", len(certificates), cutoff)
    return len(certificates)
