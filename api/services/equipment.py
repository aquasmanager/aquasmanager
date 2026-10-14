"""
Équipements : mode reçu du contrôleur et purge de l'historique des activations.
"""

import logging
from services.technical_names import firmware_name_column
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models.equipment import Equipment
from models.equipment_activation import EquipmentActivation


class EquipmentService:

    @staticmethod
    def purge_old_activations(db: Session, retention_days: int) -> int:
        """
        Supprime les activations d'équipement (historique ON/OFF) plus
        vieilles que retention_days. Sans ça, la table grossirait
        indéfiniment (une ligne par cycle réel de chaque équipement).
        """
        cutoff = datetime.now() - timedelta(days=retention_days)
        deleted = (
            db.query(EquipmentActivation)
            .filter(EquipmentActivation.started_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        if deleted:
            logging.info(f"Purge des activations d'équipement : {deleted} ligne(s) de plus de {retention_days}j supprimée(s).")
        return deleted

    @staticmethod
    def update_mode(db: Session, equipment_identifier: str, mode: str) -> Equipment | None:
        """Met à jour le mode (AUTO/MANUAL) d'un équipement en base de données."""
        equipment = db.query(Equipment).filter(firmware_name_column(Equipment) == equipment_identifier).first()
        if equipment:
            equipment.mode = mode.upper()
            db.commit()
            db.refresh(equipment)
            logging.info(f"Équipement {equipment.name} ({equipment_identifier}) mis en mode : {equipment.mode}")
            return equipment

        logging.warning(f"Équipement introuvable pour la mise à jour du mode : {equipment_identifier}")
        return None