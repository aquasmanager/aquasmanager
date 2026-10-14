"""
Boutures et certificats de cession : numérotation, création d'un
certificat à partir de boutures, signature par l'acquéreur.
"""

import secrets
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.frag import Frag, FragMovement
from pro.models.transfer_certificate import SaleLocation, SellerProfile, TransferCertificate, TransferCertificateItem
from services.privacy import effective_notice

# Durée de validité du lien de signature, puis de téléchargement du PDF signé
SIGN_LINK_DAYS = 14
SIGNED_LINK_DAYS = 90


DEFAULT_LEGAL_MENTION = (
    "Le cédant certifie que les coraux désignés ci-dessus sont des boutures obtenues en captivité "
    "à partir de colonies mères qu'il détient légalement, dont le numéro CITES et la provenance "
    "sont indiqués pour chaque bouture. L'acquéreur reconnaît avoir reçu les spécimens désignés et "
    "s'engage à conserver le présent certificat, qui justifie de leur origine, et à le transmettre "
    "en cas de cession ultérieure."
)

SELLER_REQUIRED = ("first_name", "last_name", "address", "postal_code", "city")


def log_movement(
    db: Session, frag: Frag, delta: int, reason: str, note: Optional[str] = None, certificate_number: Optional[str] = None
) -> None:
    if delta or note:
        db.add(FragMovement(frag_id=frag.id, delta=delta, reason=reason, note=note, certificate_number=certificate_number))


def backfill_movements(db: Session) -> int:
    """Lots créés avant l'historique : un mouvement « created » reconstitué (disponible + réservé + cédé)."""
    known = {frag_id for (frag_id,) in db.query(FragMovement.frag_id).distinct()}
    frags = [frag for frag in db.query(Frag).all() if frag.id not in known]
    attach_counts(db, frags)
    for frag in frags:
        total = frag.quantity + frag.reserved_quantity + frag.transferred_quantity
        db.add(FragMovement(frag_id=frag.id, delta=total, reason="created", created_at=frag.created_at))
    db.commit()
    return len(frags)


def next_number(db: Session, column, prefix: str) -> str:
    """« B-2026-0001 » : compteur annuel par préfixe (column : colonne du numéro)."""
    stem = f"{prefix}-{date.today().year}-"
    last = db.query(func.max(column)).filter(column.like(f"{stem}%")).scalar()
    counter = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{stem}{counter:04d}"


def get_seller_profile(db: Session) -> SellerProfile:
    profile = db.get(SellerProfile, 1)
    if profile is None:
        profile = SellerProfile(id=1, legal_mention=DEFAULT_LEGAL_MENTION)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def seller_is_complete(profile: SellerProfile) -> bool:
    return all(getattr(profile, field).strip() for field in SELLER_REQUIRED) and bool(profile.signature)


def seller_snapshot(profile: SellerProfile) -> dict:
    return {
        field: getattr(profile, field)
        for field in ("first_name", "last_name", "address", "postal_code", "city", "email", "phone")
    }


def attach_counts(db: Session, frags: list[Frag]) -> list[Frag]:
    """Renseigne reserved_quantity / transferred_quantity (certificats en attente / signés)."""
    ids = [frag.id for frag in frags]
    if not ids:
        return frags
    rows = (
        db.query(TransferCertificateItem.frag_id, TransferCertificate.status, func.sum(TransferCertificateItem.quantity))
        .join(TransferCertificate, TransferCertificate.id == TransferCertificateItem.certificate_id)
        .filter(TransferCertificateItem.frag_id.in_(ids))
        .group_by(TransferCertificateItem.frag_id, TransferCertificate.status)
        .all()
    )
    counts: dict[tuple[int, str], int] = {(frag_id, status): int(total or 0) for frag_id, status, total in rows}
    for frag in frags:
        frag.reserved_quantity = counts.get((frag.id, "draft"), 0)
        frag.transferred_quantity = counts.get((frag.id, "signed"), 0)
    return frags


def refresh_frag_status(db: Session, frag: Frag) -> None:
    """available s'il en reste, sinon reserved / transferred / empty."""
    attach_counts(db, [frag])
    if frag.quantity > 0:
        frag.status = "available"
    elif frag.reserved_quantity:
        frag.status = "reserved"
    elif frag.transferred_quantity:
        frag.status = "transferred"
    else:
        frag.status = "empty"


def clean_location_name(name: str) -> str:
    return " ".join(name.split())


def find_location(db: Session, name: str) -> Optional[SaleLocation]:
    """Recherche sans tenir compte de la casse ni des espaces en trop."""
    wanted = clean_location_name(name).lower()
    return next((loc for loc in db.query(SaleLocation).all() if loc.name.lower() == wanted), None)


def resolve_location(db: Session, location_id: Optional[int], location_name: Optional[str]) -> Optional[SaleLocation]:
    """Lieu existant par id, ou retrouvé / créé par son nom ; None si rien n'est indiqué."""
    if location_id is not None:
        location = db.get(SaleLocation, location_id)
        if location is None:
            raise HTTPException(status_code=400, detail="Lieu de vente inconnu.")
        return location
    name = clean_location_name(location_name or "")
    if not name:
        return None
    location = find_location(db, name)
    if location is None:
        location = SaleLocation(name=name)
        db.add(location)
        db.flush()
    return location


def create_certificate(
    db: Session,
    items: list[tuple[int, int, Optional[float]]],
    transfer_date: Optional[date],
    notes: Optional[str],
    location: Optional[SaleLocation] = None,
    allow_shortfall: bool = False,
) -> TransferCertificate:
    """
    items : (frag_id, quantité cédée, prix unitaire). Les quantités sont réservées.
    allow_shortfall : vente déjà faite (hors connexion) enregistrée même si le
    stock connu est insuffisant ; le lot est alors ramené à 0.
    """
    profile = get_seller_profile(db)
    if not seller_is_complete(profile):
        raise HTTPException(
            status_code=400,
            detail="Renseigne d'abord tes informations de cédant (nom, adresse, signature).",
        )
    frag_ids = [frag_id for frag_id, _, _ in items]
    if len(set(frag_ids)) != len(frag_ids):
        raise HTTPException(status_code=400, detail="Une bouture apparaît deux fois.")
    frags = {frag.id: frag for frag in db.query(Frag).filter(Frag.id.in_(frag_ids)).all()}
    if any(frag_id not in frags for frag_id in frag_ids):
        raise HTTPException(status_code=404, detail="Bouture introuvable.")
    too_many = [
        f"{frags[frag_id].reference} ({frags[frag_id].quantity} disponible{'s' if frags[frag_id].quantity > 1 else ''})"
        for frag_id, quantity, _ in items
        if quantity > frags[frag_id].quantity
    ]
    if too_many and not allow_shortfall:
        raise HTTPException(status_code=409, detail=f"Quantité insuffisante : {', '.join(too_many)}.")

    certificate = TransferCertificate(
        number=next_number(db, TransferCertificate.number, "C"),
        status="draft",
        transfer_date=transfer_date or date.today(),
        notes=notes or None,
        location_id=location.id if location else None,
        seller=seller_snapshot(profile),
        seller_signature=profile.signature,
        legal_mention=profile.legal_mention or DEFAULT_LEGAL_MENTION,
        privacy_notice=effective_notice(profile),
        sign_token=secrets.token_urlsafe(32),
        token_expires_at=datetime.now() + timedelta(days=SIGN_LINK_DAYS),
    )
    for frag_id, quantity, price in items:
        frag = frags[frag_id]
        certificate.items.append(
            TransferCertificateItem(
                frag_id=frag.id,
                reference=frag.reference,
                name=frag.name,
                scientific_name=frag.scientific_name,
                cites=frag.cites,
                origin=frag.origin,
                mother_name=frag.mother_name,
                mother_acquired_from=frag.acquired_from,
                cut_date=frag.cut_date,
                quantity=quantity,
                price=price if price is not None else frag.price,
            )
        )
        taken = min(quantity, frag.quantity) if allow_shortfall else quantity
        frag.quantity -= taken
        log_movement(db, frag, -taken, "reserved", certificate_number=certificate.number)
        if taken < quantity:
            log_movement(
                db, frag, 0, "correction",
                note=f"Vente hors connexion : {quantity - taken} bouture(s) de plus que le stock connu",
                certificate_number=certificate.number,
            )
    db.add(certificate)
    db.flush()
    for frag in frags.values():
        frag.certificate_id = certificate.id
        refresh_frag_status(db, frag)
    db.commit()
    db.refresh(certificate)
    return certificate


def release_frags(db: Session, certificate: TransferCertificate) -> None:
    """Certificat abandonné : les quantités réservées reviennent dans leurs lots."""
    returned = {item.frag_id: item.quantity for item in certificate.items if item.frag_id}
    frags = db.query(Frag).filter(Frag.id.in_(returned)).all() if returned else []
    for frag in frags:
        frag.quantity += returned[frag.id]
        log_movement(db, frag, returned[frag.id], "released", certificate_number=certificate.number)
        if frag.certificate_id == certificate.id:
            frag.certificate_id = None
    db.delete(certificate)
    db.flush()
    for frag in frags:
        refresh_frag_status(db, frag)


def get_by_token(db: Session, token: str) -> TransferCertificate:
    certificate = db.query(TransferCertificate).filter(TransferCertificate.sign_token == token).first()
    if certificate is None or certificate.token_expires_at < datetime.now():
        raise HTTPException(status_code=404, detail="Lien invalide ou expiré. Demande un nouveau lien au cédant.")
    return certificate


def sign_certificate(
    db: Session, certificate: TransferCertificate, buyer: dict, signature: str, signed_at: Optional[datetime] = None
) -> None:
    if certificate.status != "draft":
        raise HTTPException(status_code=409, detail="Ce certificat est déjà signé.")
    certificate.buyer = buyer
    certificate.buyer_signature = signature
    certificate.status = "signed"
    certificate.signed_at = signed_at or datetime.now()
    # Le lien reste valable pour télécharger le PDF signé
    certificate.token_expires_at = datetime.now() + timedelta(days=SIGNED_LINK_DAYS)
    db.flush()
    frag_ids = [item.frag_id for item in certificate.items if item.frag_id]
    for frag in db.query(Frag).filter(Frag.id.in_(frag_ids)).all():
        frag.certificate_id = certificate.id
        refresh_frag_status(db, frag)
    db.commit()


def frag_stats(db: Session, group_by: str) -> list[dict]:
    """
    Bilan par espèce (nom scientifique, sinon nom) ou par pied mère :
    produites = créées + ajoutées ; survie = 1 - pertes / produites.
    """
    frags = attach_counts(db, db.query(Frag).all())
    movements: dict[int, dict[str, int]] = {}
    for frag_id, reason, total in (
        db.query(FragMovement.frag_id, FragMovement.reason, func.sum(FragMovement.delta))
        .group_by(FragMovement.frag_id, FragMovement.reason)
        .all()
    ):
        movements.setdefault(frag_id, {})[reason] = int(total or 0)

    rows: dict[str, dict] = {}
    for frag in frags:
        if group_by == "mother":
            key = f"mother-{frag.mother_coral_id}" if frag.mother_coral_id else f"name-{frag.mother_name or '—'}"
            name, scientific = frag.mother_name or "Sans pied mère", frag.scientific_name
        else:
            key = (frag.scientific_name or frag.name).strip().lower()
            name, scientific = frag.name, frag.scientific_name
        row = rows.setdefault(
            key,
            {"key": key, "name": name, "scientific_name": scientific, "lots": 0, "produced": 0, "transferred": 0,
             "reserved": 0, "lost": 0, "gift": 0, "available": 0},
        )
        m = movements.get(frag.id, {})
        row["lots"] += 1
        row["produced"] += m.get("created", 0) + m.get("added", 0)
        row["lost"] += -m.get("lost", 0)
        row["gift"] += -m.get("gift", 0)
        row["transferred"] += frag.transferred_quantity
        row["reserved"] += frag.reserved_quantity
        row["available"] += frag.quantity
    for row in rows.values():
        row["survival_rate"] = round(1 - row["lost"] / row["produced"], 3) if row["produced"] else None
    return sorted(rows.values(), key=lambda r: -r["produced"])
