"""
Outils partagés : inversion des relais (contact NO/NC), unicité des noms,
notification des contrôleurs à mettre à jour, noms techniques, purge des journaux.
"""

from typing import Optional
import json
import logging
from datetime import datetime, timedelta
import sqlite3
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.equipment import Equipment
from models.sensor import Sensor
from drivers.mqtt import mqtt_driver

logger = logging.getLogger(__name__)


def calculate_inversion(relay_type: str, physical_contact: str) -> bool:
    """
    Détermine si l'ESP32 doit inverser son signal GPIO.
    relay_type: "ACTIVE_HIGH" (3.3V active) ou "ACTIVE_LOW" (0V active)
    physical_contact: "NO" (Normalement Ouvert) ou "NC" (Normalement Clos)
    """
    logic_inverted = (relay_type == "ACTIVE_LOW")

    if physical_contact == "NC":
        logic_inverted = not logic_inverted

    return logic_inverted


def notify_controller_update(controller_id: int, db: Session) -> bool:
    """
    Prévient l'ESP32 qu'une nouvelle configuration est disponible
    """
    topic = f"controller/{controller_id}/config/update"
    payload = {
        "action": "RELOAD_CONFIG",
        "timestamp": datetime.now().isoformat(),
    }

    mqtt_driver.publish(topic, json.dumps(payload), qos=1, retain=False)

    return True


def validate_entity_name_uniqueness(
    db: Session, name: str, entity_type: str, aquarium_id: Optional[int], entity_id: Optional[int] = None
):
    """
    Nom affiché unique au sein d'un même aquarium (capteurs et équipements
    confondus) ; deux aquariums peuvent avoir chacun leur « Température ».
    entity_type : 'sensor' ou 'equipment'.
    """
    normalized_name = name.strip().lower()
    for model, kind, label in ((Sensor, "sensor", "un capteur"), (Equipment, "equipment", "un équipement")):
        query = db.query(model).filter(func.lower(model.name) == normalized_name)
        if aquarium_id is not None:
            query = query.filter(model.aquarium_id == aquarium_id)
        existing = query.first()
        if existing and (entity_type != kind or existing.id != entity_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Le nom « {name} » est déjà utilisé par {label} de cet aquarium.",
            )


# Noms techniques des équipements et capteurs : services/technical_names.py


def generate_technical_name(name: str) -> str:
    """
    Transforme un nom lisible en nom technique normalisé.
    Ex: "Pompe de Remontée #1" -> "pompe_de_remontee_1"
    """
    if not name:
        return ""
    return (
        name.lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("à", "a")
    )


def purge_old_logs(db_path: str = "aquarium.db", retention_days: int = 30, run_vacuum: bool = True) -> dict:
    """
    Supprime les logs SQLite antérieurs à la période de rétention
    et libère l'espace disque physique (VACUUM).
    """
    cutoff_date = datetime.now() - timedelta(days=retention_days)

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM logs WHERE timestamp < ?",
                (cutoff_date.isoformat(),)
            )
            deleted_count = cursor.rowcount
            conn.commit()

            logger.info(f"Purge des logs : {deleted_count} anciennes entrées supprimées (rétention : {retention_days}j).")

            if run_vacuum and deleted_count > 0:
                logger.info("Optimisation de la base de données (VACUUM)...")
                conn.execute("VACUUM;")
                logger.info("Optimisation terminée.")

        return {"status": "success", "deleted_rows": deleted_count}

    except Exception as e:
        logger.error(f"Erreur lors de la purge SQLite : {e}")
        return {"status": "error", "message": str(e)}