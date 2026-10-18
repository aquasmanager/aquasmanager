"""
group_orders.py

Commandes groupées (VPC) entre passionnés d'un même secteur : relais vers le
hub de l'éditeur (settings.hub_url), qui garde les annonces. L'installation
garde ses jetons (GroupOrderLink) et ses départements suivis ; chaque heure,
elle signale les nouvelles annonces de son secteur et les nouveaux
participants de ses propres annonces.
"""

import hashlib
import logging
from typing import Optional

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.group_order import GroupOrderLink, GroupOrderSettings
from settings import settings

logger = logging.getLogger(__name__)

TIMEOUT = 10


def enabled() -> bool:
    return bool(settings.hub_url) and settings.hub_url.lower() != "none"


def _installation() -> str:
    """Identifiant d'installation pour les limites anti-abus du hub (empreinte, pas l'identifiant)."""
    from services.license import current_status

    return hashlib.sha256(current_status().instance_id.encode()).hexdigest()[:32]


def hub(method: str, path: str, token: Optional[str] = None, client: Optional[httpx.Client] = None, **kwargs):
    """Appel au hub ; ses refus (404, 409, 422, 429...) sont relayés tels quels."""
    if settings.demo:
        # Démo publique : annonces d'exemple, rien n'est envoyé au vrai hub
        from services.demo import demo_group_orders_hub

        return demo_group_orders_hub(method, path, token, **kwargs)
    if not enabled():
        raise HTTPException(status_code=503, detail="Commandes groupées indisponibles : hub désactivé.")
    headers = {"X-Installation": _installation()}
    if token:
        headers["X-Token"] = token
    url = f"{settings.hub_url.rstrip('/')}/v1/group-orders{path}"
    try:
        http = client or httpx.Client(timeout=TIMEOUT)
        try:
            response = http.request(method, url, headers=headers, **kwargs)
        finally:
            if client is None:
                http.close()
    except httpx.HTTPError as e:
        logger.warning("Hub injoignable (%s %s) : %s", method, path, e)
        raise HTTPException(status_code=502, detail="Le service des commandes groupées ne répond pas. Réessaie plus tard.")
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = None
        if isinstance(detail, list):  # erreur de validation
            detail = "; ".join(str(d.get("msg", "")).removeprefix("Value error, ") for d in detail)
        raise HTTPException(status_code=response.status_code if response.status_code < 500 else 502,
                            detail=detail or "Le service des commandes groupées a refusé la demande.")
    return response.json() if response.content else None


def get_settings(db: Session) -> GroupOrderSettings:
    row = db.get(GroupOrderSettings, 1)
    if row is None:
        row = GroupOrderSettings(id=1, departments=[], notify=True, seen_ids=[])
        db.add(row)
        db.commit()
    return row


def link_for(db: Session, hub_id: str) -> Optional[GroupOrderLink]:
    """Jeton de l'installation pour cette annonce (organisateur d'abord)."""
    links = db.query(GroupOrderLink).filter(GroupOrderLink.hub_id == hub_id).all()
    return next((link for link in links if link.role == "owner"), links[0] if links else None)


def check_news(db: Session, client: Optional[httpx.Client] = None) -> list[str]:
    """Nouvelles annonces du secteur suivi et nouveaux participants : notification. Retourne les messages."""
    from services.notify import dispatch_alert

    if not enabled():
        return []
    conf = get_settings(db)
    messages: list[str] = []
    if conf.departments:
        orders = hub("GET", "", params={"departments": ",".join(conf.departments)}, client=client)
        mine = {link.hub_id for link in db.query(GroupOrderLink).all()}
        seen = set(conf.seen_ids or [])
        fresh = [o for o in orders if o["id"] not in seen and o["id"] not in mine and o["status"] == "open"]
        if fresh and conf.notify:
            messages += [f"{o['title']} — {o['shop']} ({o['department']}, {o['area']}), jusqu'au {o['deadline']}" for o in fresh]
        # Liste des annonces encore en ligne : la mémoire ne grossit pas indéfiniment
        conf.seen_ids = [o["id"] for o in orders]
    for link in db.query(GroupOrderLink).filter(GroupOrderLink.role == "owner").all():
        try:
            order = hub("GET", f"/{link.hub_id}", token=link.token, client=client)
        except HTTPException as e:
            if e.status_code == 404:  # annonce supprimée ou purgée
                db.delete(link)
            continue
        count = order["participants"]
        if count > link.known_members and conf.notify:
            names = ", ".join(m["name"] for m in order["members"][link.known_members:])
            messages.append(f"« {link.title} » : {count} participant(s), nouveau : {names}")
        link.known_members = count
    db.commit()
    if messages:
        dispatch_alert(
            "[AquasManager] Commandes groupées" if len(messages) > 1 else "[AquasManager] Commande groupée",
            "\n".join(f"• {m}" for m in messages),
            priority="low",
        )
    return messages
