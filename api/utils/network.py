"""
Réseau : première adresse IP libre de la plage réservée aux contrôleurs.
"""

import ipaddress
import logging
from typing import Optional
from sqlalchemy.orm import Session
from models.controller import Controller
from settings import settings  # Import de l'instance globale 'settings' (en minuscules)

logger = logging.getLogger(__name__)


def get_next_available_ip(
    db: Session,
    start_ip: Optional[str] = None,
    end_ip: Optional[str] = None
) -> Optional[str]:
    """
    Parcourt la plage d'IP spécifiée (ou celle issue de settings.network)
    et retourne la première IP qui n'est pas encore attribuée à un contrôleur en BDD.
    """
    start_str = start_ip or settings.network.start
    end_str = end_ip or settings.network.end

    try:
        start = ipaddress.IPv4Address(start_str)
        end = ipaddress.IPv4Address(end_str)
    except ValueError as e:
        raise ValueError(f"Format d'adresse IP invalide : {e}")

    if start > end:
        raise ValueError("L'IP de début doit être inférieure ou égale à l'IP de fin.")

    used_ips = {
        c.ip for c in db.query(Controller.ip).filter(Controller.ip.isnot(None)).all()
    }

    current = start
    while current <= end:
        ip_str = str(current)
        if ip_str not in used_ips:
            return ip_str
        current += 1

    logger.warning(f"Aucune adresse IP disponible dans la plage {start_str} - {end_str}")
    return None