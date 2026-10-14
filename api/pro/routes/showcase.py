"""
showcase.py (routes)

Vitrine des boutures (sans compte) et réservations des visiteurs ;
côté propriétaire : réglages, liens de partage, lots masqués, réservations.

Accès visiteur, dans cet ordre :
- lien de partage (?t=jeton) : valable entre ses dates, tant qu'il n'est pas révoqué ;
- lien permanent /vitrine, s'il est ouvert dans les réglages ;
- sinon, lien de partage actif marqué « étiquettes QR » (bourse en cours).
"""

import logging
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from middleware.auth import FRAG_ROLES, min_role_required
from services.license import require_feature
from middleware.database import get_db
from models.frag import Frag
from pro.models.showcase import ShowcaseLink, ShowcaseReservation, ShowcaseSettings
from pro.schemas.showcase import (
    PublicShowcase,
    ShowcaseLinkCreate,
    ShowcaseLinkRead,
    ShowcaseLinkUpdate,
    ReservationConfirm,
    ReservationCreate,
    ReservationRead,
    ShowcaseSettingsBase,
    ShowcaseSettingsRead,
)
from pro.schemas.transfer_certificate import CertificateRead
from services import notify
from services.frags import create_certificate, resolve_location

logger = logging.getLogger(__name__)

# Bourse : réservée à une licence qui l'inclut (vitrine publique comprise)
router = APIRouter(prefix="/showcase", tags=["showcase"], dependencies=[Depends(require_feature("bourse")), Depends(min_role_required("consult"))])
public_router = APIRouter(prefix="/public/showcase", tags=["public"], dependencies=[Depends(require_feature("bourse"))])
EXTRA_ROUTERS = (public_router,)

# Anti-abus : réservations par adresse IP et par heure
RESERVATIONS_PER_HOUR = 5
_recent: dict[str, deque] = defaultdict(deque)


def get_settings(db: Session) -> ShowcaseSettings:
    settings = db.get(ShowcaseSettings, 1)
    if settings is None:
        settings = ShowcaseSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def _visible_lots(db: Session) -> list[Frag]:
    return (
        db.query(Frag)
        .filter(Frag.quantity > 0, Frag.showcase_hidden.is_(False))
        .order_by(Frag.name, Frag.reference)
        .all()
    )


def _resolve_access(db: Session, token: Optional[str]) -> tuple[ShowcaseSettings, Optional[ShowcaseLink]]:
    """Réglages et lien de partage utilisé (None = lien permanent) ; 404 si la vitrine est fermée."""
    settings = get_settings(db)
    if token:
        link = db.query(ShowcaseLink).filter(ShowcaseLink.token == token).first()
        if link is None or link.state != "active":
            raise HTTPException(status_code=404, detail="Ce lien de vitrine a expiré ou n'est plus valable.")
        return settings, link
    if settings.enabled:
        return settings, None
    for link in db.query(ShowcaseLink).filter(ShowcaseLink.qr_labels.is_(True), ShowcaseLink.revoked.is_(False)):
        if link.state == "active":
            return settings, link
    raise HTTPException(status_code=404, detail="Vitrine indisponible.")


# Pages publiques : hors des moteurs de recherche
NOINDEX = {"X-Robots-Tag": "noindex, nofollow"}


# --- Public ---


@public_router.get("/", response_model=PublicShowcase)
def public_showcase(response: Response, t: Optional[str] = Query(default=None, max_length=64), db: Session = Depends(get_db)):
    response.headers.update(NOINDEX)
    settings, link = _resolve_access(db, t)
    if link is not None:
        link.view_count += 1
        link.last_viewed_at = datetime.now()
        db.commit()
    return {
        "title": settings.title,
        "intro": settings.intro,
        "contact": settings.contact,
        "show_prices": settings.show_prices,
        "price_label": settings.price_label,
        "allow_reservations": settings.allow_reservations,
        "link_label": link.label if link else None,
        "ends_on": link.ends_on if link else None,
        "lots": [
            {
                "id": f.id,
                "reference": f.reference,
                "name": f.name,
                "scientific_name": f.scientific_name,
                "coral_type": f.coral_type,
                "quantity": f.quantity,
                "price": f.price if settings.show_prices else None,
            }
            for f in _visible_lots(db)
        ],
    }


@public_router.post("/reservations", status_code=status.HTTP_201_CREATED)
def reserve(
    payload: ReservationCreate,
    request: Request,
    response: Response,
    t: Optional[str] = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
):
    response.headers.update(NOINDEX)
    settings, link = _resolve_access(db, t)
    if not settings.allow_reservations:
        raise HTTPException(status_code=404, detail="Réservations indisponibles.")

    ip = request.client.host if request.client else "?"
    now = time.monotonic()
    recent = _recent[ip]
    while recent and now - recent[0] > 3600:
        recent.popleft()
    if len(recent) >= RESERVATIONS_PER_HOUR:
        raise HTTPException(status_code=429, detail="Trop de réservations envoyées. Réessaie plus tard.")

    lots = {f.id: f for f in _visible_lots(db)}
    items = []
    for item in payload.items:
        frag = lots.get(item.frag_id)
        if frag is None:
            raise HTTPException(status_code=409, detail="Une des boutures n'est plus disponible.")
        if item.quantity > frag.quantity:
            raise HTTPException(status_code=409, detail=f"{frag.name} : seulement {frag.quantity} disponible(s).")
        items.append({"frag_id": frag.id, "quantity": item.quantity, "reference": frag.reference, "name": frag.name})

    reservation = ShowcaseReservation(
        name=payload.name.strip(),
        contact=payload.contact.strip(),
        message=payload.message,
        items=items,
        link_id=link.id if link else None,
    )
    db.add(reservation)
    db.commit()
    recent.append(now)

    summary = ", ".join(f"{i['quantity']} × {i['name']}" for i in items)
    try:
        notify.dispatch_alert(
            "Nouvelle réservation de boutures",
            f"{reservation.name} ({reservation.contact}) réserve : {summary}."
            + (f"\nVia le lien : {link.label}" if link else "")
            + (f"\nMessage : {reservation.message}" if reservation.message else ""),
        )
    except Exception:
        logger.exception("Notification de réservation impossible")
    return {"ok": True}


# --- Propriétaire ---


@router.get("/settings", response_model=ShowcaseSettingsRead)
def read_settings(db: Session = Depends(get_db)):
    return get_settings(db)


@router.put(
    "/settings",
    response_model=ShowcaseSettingsRead,
    dependencies=[Depends(min_role_required("user", also=FRAG_ROLES))],
)
def update_settings(payload: ShowcaseSettingsBase, db: Session = Depends(get_db)):
    settings = get_settings(db)
    for field, value in payload.model_dump().items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return settings


# --- Liens de partage ---

LINK_WRITE = [Depends(min_role_required("user", also=FRAG_ROLES))]


def _link_or_404(db: Session, link_id: int) -> ShowcaseLink:
    link = db.get(ShowcaseLink, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Lien non trouvé")
    return link


def _check_dates(link: ShowcaseLink) -> None:
    if link.starts_on and link.ends_on and link.ends_on < link.starts_on:
        raise HTTPException(status_code=400, detail="La date de fin doit suivre la date de début.")


@router.get("/links", response_model=List[ShowcaseLinkRead])
def list_links(db: Session = Depends(get_db)):
    return db.query(ShowcaseLink).order_by(ShowcaseLink.id.desc()).all()


@router.post("/links", response_model=ShowcaseLinkRead, status_code=status.HTTP_201_CREATED, dependencies=LINK_WRITE)
def create_link(payload: ShowcaseLinkCreate, db: Session = Depends(get_db)):
    location = resolve_location(db, payload.location_id, payload.location_name)
    link = ShowcaseLink(
        token=secrets.token_urlsafe(18),
        label=payload.label.strip(),
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        qr_labels=payload.qr_labels,
        location_id=location.id if location else None,
    )
    _check_dates(link)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.patch("/links/{link_id}", response_model=ShowcaseLinkRead, dependencies=LINK_WRITE)
def update_link(link_id: int, payload: ShowcaseLinkUpdate, db: Session = Depends(get_db)):
    link = _link_or_404(db, link_id)
    data = payload.model_dump(exclude_unset=True)
    if "location_id" in data or "location_name" in data:
        location = resolve_location(db, data.pop("location_id", None), data.pop("location_name", None))
        link.location_id = location.id if location else None
    for field, value in data.items():
        if field == "label":
            value = (value or "").strip() or link.label
        setattr(link, field, value)
    _check_dates(link)
    db.commit()
    db.refresh(link)
    return link


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=LINK_WRITE)
def delete_link(link_id: int, db: Session = Depends(get_db)):
    db.delete(_link_or_404(db, link_id))
    db.commit()


# --- Réservations ---


@router.get("/reservations", response_model=List[ReservationRead])
def list_reservations(db: Session = Depends(get_db)):
    return db.query(ShowcaseReservation).order_by(ShowcaseReservation.id.desc()).all()


def _reservation_or_404(db: Session, reservation_id: int) -> ShowcaseReservation:
    reservation = db.get(ShowcaseReservation, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Réservation non trouvée")
    return reservation


@router.post(
    "/reservations/{reservation_id}/confirm",
    response_model=CertificateRead,
    dependencies=[Depends(min_role_required("user", also=FRAG_ROLES))],
)
def confirm(reservation_id: int, payload: ReservationConfirm, db: Session = Depends(get_db)):
    """Crée le certificat en attente de signature : les boutures sont mises de côté."""
    from pro.routes.transfer_certificate import _full

    reservation = _reservation_or_404(db, reservation_id)
    if reservation.status != "new":
        raise HTTPException(status_code=409, detail="Réservation déjà traitée.")
    location = resolve_location(db, payload.location_id, payload.location_name)
    if location is None and reservation.link is not None:
        # Réservation faite via le lien d'une bourse : même lieu par défaut
        location = reservation.link.location
    certificate = create_certificate(
        db,
        [(item["frag_id"], item["quantity"], None) for item in reservation.items],
        None,
        f"Réservation de {reservation.name} ({reservation.contact})",
        location,
    )
    reservation.status = "confirmed"
    reservation.certificate_id = certificate.id
    db.commit()
    return _full(certificate)


@router.post(
    "/reservations/{reservation_id}/decline",
    response_model=ReservationRead,
    dependencies=[Depends(min_role_required("user", also=FRAG_ROLES))],
)
def decline(reservation_id: int, db: Session = Depends(get_db)):
    reservation = _reservation_or_404(db, reservation_id)
    if reservation.status != "new":
        raise HTTPException(status_code=409, detail="Réservation déjà traitée.")
    reservation.status = "declined"
    db.commit()
    db.refresh(reservation)
    return reservation


@router.delete(
    "/reservations/{reservation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("user", also=FRAG_ROLES))],
)
def delete_reservation(reservation_id: int, db: Session = Depends(get_db)):
    db.delete(_reservation_or_404(db, reservation_id))
    db.commit()
