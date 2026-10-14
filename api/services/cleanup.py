"""
Suppression propre des données liées.

SQLite n'applique pas les ON DELETE CASCADE / SET NULL des clés étrangères
(PRAGMA foreign_keys désactivé) : sans ce nettoyage explicite, supprimer un
équipement, un capteur ou un aquarium laisse des lignes orphelines (alertes
bloquées dans le bandeau, photos réattribuées à un nouvel élément qui
récupère le même id, broches marquées occupées...).
"""

import logging
import os
import shutil
from datetime import datetime

from sqlalchemy.orm import Session

from models.aquarium import Aquarium
from models.controller import Controller
from models.dashboard_card import DashboardCard
from models.equipment import Equipment
from models.fault import EquipmentFault
from models.metric_alert import MetricAlert
from models.frag import Frag
from models.photo import Photo, PhotoType
from models.rule import Rule
from models.sensor import Sensor
from models.water_parameter import IcpImportBatch
from services.pins import claim_pin, release_pin_if_unused
from services.shared_scope import detach_aquarium

logger = logging.getLogger(__name__)

PHOTO_ROOT = "uploads"
ICP_PDF_DIR = os.path.join("uploads", "icp")


def delete_photos(db: Session, entity_type: PhotoType, entity_id: int) -> None:
    """Supprime les photos (lignes + fichiers) d'un élément."""
    db.query(Photo).filter(Photo.entity_type == entity_type, Photo.entity_id == entity_id).delete(
        synchronize_session=False
    )
    folder = os.path.join(PHOTO_ROOT, entity_type.value, str(entity_id))
    try:
        if os.path.isdir(folder):
            shutil.rmtree(folder)
    except OSError as err:
        logger.error("Suppression du dossier %s impossible : %s", folder, err)


def _mark_dirty(db: Session, controller_ids: set[int]) -> None:
    for controller in db.query(Controller).filter(Controller.id.in_(controller_ids)).all():
        controller.is_dirty = True


def _delete_equipment_dependencies(db: Session, equipment: Equipment) -> None:
    db.query(EquipmentFault).filter(EquipmentFault.equipment_id == equipment.id).delete(synchronize_session=False)
    db.query(DashboardCard).filter(DashboardCard.equipment_id == equipment.id).update(
        {DashboardCard.equipment_id: None}, synchronize_session=False
    )


def _delete_sensor_dependencies(db: Session, sensor: Sensor) -> None:
    # Les conditions de règle et les relevés partent en cascade avec le capteur
    for column in (DashboardCard.sensor_id, DashboardCard.sensor_high_id, DashboardCard.sensor_low_id):
        db.query(DashboardCard).filter(column == sensor.id).update({column: None}, synchronize_session=False)
    db.query(MetricAlert).filter(MetricAlert.sensor_id == sensor.id, MetricAlert.resolved_at.is_(None)).update(
        {MetricAlert.resolved_at: datetime.now()}, synchronize_session=False
    )


def _delete_rules_without_conditions(db: Session) -> None:
    """Une règle dont tous les capteurs ont été supprimés ne peut plus rien déclencher."""
    for rule in db.query(Rule).filter(~Rule.conditions.any()).all():
        logger.info("Règle « %s » supprimée : plus aucune condition", rule.name)
        db.delete(rule)


def delete_equipment(db: Session, equipment: Equipment) -> None:
    """Supprime l'équipement, ses défauts et libère sa broche (sans commit)."""
    pin_id = equipment.pin_id
    _mark_dirty(db, {equipment.controller_id})
    _delete_equipment_dependencies(db, equipment)
    db.delete(equipment)
    db.flush()
    release_pin_if_unused(db, pin_id)


def delete_sensor(db: Session, sensor: Sensor) -> None:
    """Supprime le capteur et libère sa broche si plus aucune sonde ne l'utilise (sans commit)."""
    pin_id = sensor.pin_id
    _mark_dirty(db, {sensor.controller_id})
    _delete_sensor_dependencies(db, sensor)
    db.delete(sensor)
    db.flush()
    release_pin_if_unused(db, pin_id)
    _delete_rules_without_conditions(db)


def delete_aquarium(db: Session, aquarium: Aquarium) -> None:
    """
    Supprime l'aquarium et tout ce qui lui appartient (sans commit). Les
    relations ORM (équipements, capteurs, lampes, vivants, paramètres,
    cartes) partent en cascade ; on s'occupe ici de ce qu'elles ne couvrent
    pas.
    """
    dirty_controllers: set[int] = set()
    freed_pins: set[int] = set()

    for equipment in aquarium.equipments:
        _delete_equipment_dependencies(db, equipment)
        dirty_controllers.add(equipment.controller_id)
        freed_pins.add(equipment.pin_id)
    for sensor in aquarium.sensors:
        _delete_sensor_dependencies(db, sensor)
        dirty_controllers.add(sensor.controller_id)
        freed_pins.add(sensor.pin_id)
    for light in aquarium.lights:
        dirty_controllers.add(light.controller_id)
        for channel in light.light_channels:
            if channel.pin is not None:
                claim_pin(channel.pin, "FREE", "FREE", "FREE")

    for entity_type, items in (
        (PhotoType.fishes, aquarium.fishes),
        (PhotoType.corals, aquarium.corals),
        (PhotoType.plants, aquarium.plants),
        (PhotoType.invertebrates, aquarium.invertebrates),
    ):
        for item in items:
            delete_photos(db, entity_type, item.id)
    delete_photos(db, PhotoType.aquariums, aquarium.id)

    # Tâches et stock : propres à l'aquarium supprimés, partagés conservés
    detach_aquarium(db, aquarium.id)
    # Boutures : conservées (historique des cessions), sans aquarium ni pied mère
    coral_ids = [coral.id for coral in aquarium.corals]
    db.query(Frag).filter(Frag.aquarium_id == aquarium.id).update({Frag.aquarium_id: None}, synchronize_session=False)
    if coral_ids:
        db.query(Frag).filter(Frag.mother_coral_id.in_(coral_ids)).update(
            {Frag.mother_coral_id: None}, synchronize_session=False
        )
    db.query(MetricAlert).filter(MetricAlert.aquarium_id == aquarium.id).delete(synchronize_session=False)
    for batch in db.query(IcpImportBatch).filter(IcpImportBatch.aquarium_id == aquarium.id).all():
        pdf_path = os.path.join(ICP_PDF_DIR, f"{batch.id}.pdf")
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        db.delete(batch)

    _mark_dirty(db, dirty_controllers)
    db.delete(aquarium)
    db.flush()
    for pin_id in freed_pins:
        release_pin_if_unused(db, pin_id)
    _delete_rules_without_conditions(db)
