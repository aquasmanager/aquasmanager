"""
maintenance.py

Mode maintenance d'un aquarium (changement d'eau, nettoyage) : les équipements
choisis passent en manuel arrêtés, leur mode et leur état d'avant sont mémorisés
puis restaurés à
la fin (bouton « Terminer » ou échéance, vérifiée chaque minute). Pendant ce
temps, les alertes de température et de sonde muette de l'aquarium sont
suspendues (elles reprennent à la fin si la valeur est toujours hors cible).
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from drivers.mqtt import mqtt_driver
from models.aquarium import Aquarium
from models.equipment import Equipment, EquipmentMode
from services import technical_names

logger = logging.getLogger(__name__)

MAX_MINUTES = 8 * 60


def _publish(equipment: Equipment, suffix: str, value: str) -> None:
    controller = equipment.controller
    if controller is not None:
        topic = f"{controller.technical_name}/switch/{technical_names.firmware_name(equipment)}/{suffix}"
        mqtt_driver.publish(topic, value, qos=1)


def set_equipment_mode(equipment: Equipment, mode: str) -> None:
    """Mode (AUTO / MANUAL) en base et consigne envoyée au contrôleur."""
    equipment.mode = EquipmentMode(mode)
    _publish(equipment, "mode/set", mode)


def switch_equipment(equipment: Equipment, status: str) -> None:
    """Marche / arrêt (pris en compte en mode manuel) ; l'état réel revient du contrôleur."""
    _publish(equipment, "command", status)


def _state(equipment: Equipment) -> dict:
    mode = equipment.mode.value if hasattr(equipment.mode, "value") else str(equipment.mode)
    status = equipment.status.value if hasattr(equipment.status, "value") else str(equipment.status)
    return {"mode": mode, "status": status}


def _stop_equipment(equipment: Equipment) -> None:
    set_equipment_mode(equipment, "MANUAL")
    switch_equipment(equipment, "OFF")


def _restore_equipment(equipment: Equipment, state: dict) -> None:
    set_equipment_mode(equipment, state.get("mode", "AUTO"))
    # État d'avant renvoyé aussi en automatique : le firmware ne réévalue pas le relais
    # au retour en AUTO (une pompe sans règle resterait arrêtée)
    switch_equipment(equipment, "ON" if state.get("status") == "ON" else "OFF")


def is_active(aquarium: Aquarium, now: Optional[datetime] = None) -> bool:
    return aquarium.maintenance_until is not None and aquarium.maintenance_until > (now or datetime.now())


def paused_aquarium_ids(db: Session) -> set[int]:
    now = datetime.now()
    return {a.id for a in db.query(Aquarium).filter(Aquarium.maintenance_until.isnot(None)).all() if is_active(a, now)}


def start(db: Session, aquarium: Aquarium, equipment_ids: list[int], minutes: int) -> Aquarium:
    """Démarre (ou prolonge/modifie) la maintenance : équipements choisis arrêtés."""
    equipments = {
        e.id: e for e in db.query(Equipment).filter(Equipment.aquarium_id == aquarium.id).all()
    }
    unknown = set(equipment_ids) - set(equipments)
    if unknown:
        raise ValueError("Ces équipements n'appartiennent pas à cet aquarium.")
    saved = {int(k): v for k, v in (aquarium.maintenance_saved_modes or {}).items()} if is_active(aquarium) else {}
    # Équipement retiré de la sélection pendant une maintenance : remis tout de suite
    for eq_id in list(saved):
        if eq_id not in equipment_ids and eq_id in equipments:
            _restore_equipment(equipments[eq_id], saved.pop(eq_id))
    for eq_id in equipment_ids:
        equipment = equipments[eq_id]
        if eq_id not in saved:
            saved[eq_id] = _state(equipment)
            _stop_equipment(equipment)
    now = datetime.now()
    started = not is_active(aquarium, now)
    if started:
        aquarium.maintenance_started_at = now
    aquarium.maintenance_until = now + timedelta(minutes=minutes)
    aquarium.maintenance_equipment_ids = list(equipment_ids)
    aquarium.maintenance_saved_modes = {str(k): v for k, v in saved.items()}
    if started:
        from services import journal

        names = ", ".join(equipments[i].name for i in equipment_ids)
        journal.add(db, aquarium.id, "maintenance", f"Maintenance ({minutes} min) : {names} arrêté(s)")
    db.commit()
    logger.info("Maintenance de %s : %d équipement(s) arrêté(s) pour %d min", aquarium.name, len(equipment_ids), minutes)
    return aquarium


def stop(db: Session, aquarium: Aquarium) -> int:
    """Fin de la maintenance : chaque équipement retrouve son mode et son état d'avant. Retourne leur nombre."""
    saved = aquarium.maintenance_saved_modes or {}
    restored = 0
    for eq_id, state in saved.items():
        equipment = db.get(Equipment, int(eq_id))
        if equipment is None or equipment.aquarium_id != aquarium.id:
            continue
        _restore_equipment(equipment, state)
        restored += 1
    aquarium.maintenance_until = None
    aquarium.maintenance_started_at = None
    aquarium.maintenance_saved_modes = None
    db.commit()
    logger.info("Maintenance de %s terminée : %d équipement(s) remis", aquarium.name, restored)
    return restored


def expire_due(db: Session) -> list[str]:
    """Maintenances arrivées à échéance : équipements remis, notification envoyée."""
    from services.notify import dispatch_alert

    now = datetime.now()
    ended = []
    for aquarium in db.query(Aquarium).filter(Aquarium.maintenance_until.isnot(None)).all():
        if aquarium.maintenance_until > now:
            continue
        restored = stop(db, aquarium)
        ended.append(aquarium.name)
        dispatch_alert(
            f"[AquasManager] {aquarium.name} — fin de la maintenance",
            f"Durée écoulée : {restored} équipement(s) remis dans leur mode d'avant.",
            priority="default",
        )
    return ended
