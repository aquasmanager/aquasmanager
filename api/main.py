"""
Point d'entrée de l'API AquasManager (FastAPI).

Au chargement : tables créées, migrations légères et migrations de données
uniques, compte admin par défaut, catalogue d'espèces. Au démarrage
(lifespan) : connexion MQTT (ou données de démonstration) et tâches de fond
périodiques (purges, alertes, sondes muettes, maintenances, catalogue commun,
commandes groupées). Les routes sont chargées depuis routes/ et pro/routes/.
"""

import asyncio
import time
import json
from contextlib import asynccontextmanager
from drivers import mqtt
from middleware.logging_config import setup_logging
from middleware.log_context import LogContextMiddleware
from version import __version__
import logging
import shutil
from pathlib import Path
import bcrypt
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from middleware.auth import verify_access_token
from fastapi_swagger import patch_fastapi
from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateIndex, CreateTable
from middleware.database import Base, engine
from middleware.utc_json import UTCJSONResponse
from fastapi.middleware.cors import CORSMiddleware
from middleware.idempotency import IdempotencyMiddleware, purge_idempotency_keys
from routes import include_routes
from settings import settings
from middleware.database import SessionLocal
from services.websocket import ws_manager
from services.tools import purge_old_logs
from services.backup import purge_old_backups, run_scheduled_backup_if_due
from services.privacy import anonymize_expired
from services.frags import get_seller_profile
from services.equipment import EquipmentService
from services.metric_alerts import evaluate_metric_alerts, purge_old_metric_alerts
from services.fault import purge_old_faults
from services.species_catalog import seed_species_catalog
from services.catalog_sync import mark_customized_builtins, sync_catalog, sync_enabled
from services.sensor_staleness import clear_silent_probes
from middleware.auth import purge_expired_refresh_tokens
from middleware.audit import AuditMiddleware
from services.audit import purge_old_audit_logs
from services.retention import purge_old_sensor_readings
from services.task_reminders import send_due_today_reminders
from services.equipment_usage import check_service_due
from services.parameter_trends import check_trend_alerts
from services import demo
from services import maintenance

# Importe tous les modèles : create_all() ci-dessous crée leurs tables
import models  # noqa: F401
from models.user import User, UserRole


setup_logging()

logger = logging.getLogger(__name__)
Base.metadata.create_all(bind=engine)


def _rename_other_alives_to_invertebrates(tables: list[str]) -> None:
    """
    « Autres vivants » devient « Invertébrés » : table, photos (type et
    dossier uploads/) et journal d'activité. create_all() vient de créer une
    table invertebrates vide : elle est remplacée par l'ancienne.
    """
    if "other_alives" in tables:
        with engine.begin() as conn:
            if "invertebrates" in tables:
                if conn.execute(text("SELECT COUNT(*) FROM invertebrates")).scalar():
                    logger.error("Migration: other_alives ET invertebrates non vides, renommage ignoré")
                    return
                conn.execute(text("DROP TABLE invertebrates"))
            logger.info("Migration: renommage de la table other_alives en invertebrates")
            conn.execute(text("ALTER TABLE other_alives RENAME TO invertebrates"))
            conn.execute(text("DROP INDEX IF EXISTS ix_other_alives_id"))
            conn.execute(text("DROP INDEX IF EXISTS ix_other_alives_name"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_invertebrates_id ON invertebrates (id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_invertebrates_name ON invertebrates (name)"))

    with engine.begin() as conn:
        if "photos" in tables:
            conn.execute(text("UPDATE photos SET entity_type = 'invertebrates' WHERE entity_type = 'other_alives'"))
        if "audit_logs" in tables:
            conn.execute(text("UPDATE audit_logs SET entity_type = 'invertebrate' WHERE entity_type = 'other_alive'"))

    # Photos : uploads/other_alives/<id> -> uploads/invertebrates/<id>
    old_dir, new_dir = Path("uploads") / "other_alives", Path("uploads") / "invertebrates"
    if old_dir.is_dir():
        logger.info("Migration: déplacement des photos uploads/other_alives vers uploads/invertebrates")
        new_dir.mkdir(parents=True, exist_ok=True)
        for entry in old_dir.iterdir():
            target = new_dir / entry.name
            if target.exists():
                logger.error("Migration: %s existe déjà, %s laissé en place", target, entry)
            else:
                shutil.move(str(entry), str(target))
        if not any(old_dir.iterdir()):
            old_dir.rmdir()


def _apply_lightweight_migrations():
    """
    Le projet n'utilise pas Alembic. create_all() crée les tables
    manquantes mais ne modifie jamais les tables existantes : les nouvelles
    colonnes ajoutées à un modèle déjà en base doivent donc être ajoutées à
    la main ici, une seule fois, de façon idempotente
    """
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    _rename_other_alives_to_invertebrates(tables)
    tables = inspect(engine).get_table_names()

    if "rules" in tables:
        existing_columns = {col["name"] for col in inspector.get_columns("rules")}
        if "is_safety_lock" not in existing_columns:
            logger.info("Migration: ajout de la colonne rules.is_safety_lock")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE rules ADD COLUMN is_safety_lock BOOLEAN DEFAULT 0"))

    if "users" in tables:
        existing_user_columns = {col["name"] for col in inspector.get_columns("users")}
        if "must_change_password" not in existing_user_columns:
            logger.info("Migration: ajout de la colonne users.must_change_password")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT 0"))
        if "language" not in existing_user_columns:
            logger.info("Migration: ajout de la colonne users.language")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN language VARCHAR(5)"))

    if "dashboard_cards" in tables:
        existing_card_columns = {col["name"] for col in inspector.get_columns("dashboard_cards")}
        if "water_parameter_id" not in existing_card_columns:
            logger.info("Migration: ajout de la colonne dashboard_cards.water_parameter_id")
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE dashboard_cards ADD COLUMN water_parameter_id INTEGER REFERENCES water_parameters(id)")
                )
        if "equipment_ids" not in existing_card_columns:
            logger.info("Migration: ajout de la colonne dashboard_cards.equipment_ids")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE dashboard_cards ADD COLUMN equipment_ids JSON"))
        for column in ("period", "normal_state"):
            if column not in existing_card_columns:
                logger.info("Migration: ajout de la colonne dashboard_cards.%s", column)
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE dashboard_cards ADD COLUMN {column} VARCHAR(4)"))
        # MySQL : le type est un vrai ENUM, à étendre quand un type de carte est ajouté
        # (SQLite stocke un simple VARCHAR, sans contrainte)
        if engine.dialect.name == "mysql":
            from models.dashboard_card import DashboardCardType

            values = ", ".join(f"'{t.value}'" for t in DashboardCardType)
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE dashboard_cards MODIFY type ENUM({values}) NOT NULL"))

    if "notification_settings" in tables:
        existing_notify_columns = {col["name"] for col in inspector.get_columns("notification_settings")}
        for column, ddl in (
            ("email_enabled", "BOOLEAN NOT NULL DEFAULT 0"),
            ("smtp_host", "VARCHAR(200)"),
            ("smtp_port", "INTEGER NOT NULL DEFAULT 587"),
            ("smtp_security", "VARCHAR(10) NOT NULL DEFAULT 'starttls'"),
            ("smtp_user", "VARCHAR(200)"),
            ("smtp_password", "VARCHAR(200)"),
            ("email_from", "VARCHAR(200)"),
            ("email_to", "VARCHAR(500)"),
        ):
            if column not in existing_notify_columns:
                logger.info("Migration: ajout de la colonne notification_settings.%s", column)
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE notification_settings ADD COLUMN {column} {ddl}"))

    if "water_parameter_readings" in tables:
        existing_reading_columns = {col["name"] for col in inspector.get_columns("water_parameter_readings")}
        if "icp_batch_id" not in existing_reading_columns:
            logger.info("Migration: ajout de la colonne water_parameter_readings.icp_batch_id")
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE water_parameter_readings ADD COLUMN icp_batch_id "
                        "INTEGER REFERENCES icp_import_batches(id)"
                    )
                )

    if "water_parameters" in tables:
        existing_param_columns = {col["name"] for col in inspector.get_columns("water_parameters")}
        if "pinned" not in existing_param_columns:
            logger.info("Migration: ajout de la colonne water_parameters.pinned")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE water_parameters ADD COLUMN pinned BOOLEAN DEFAULT 0"))

    if "metric_alerts" in tables:
        existing_alert_columns = {col["name"] for col in inspector.get_columns("metric_alerts")}
        with engine.begin() as conn:
            if "maintenance_task_id" not in existing_alert_columns:
                logger.info("Migration: ajout de la colonne metric_alerts.maintenance_task_id")
                conn.execute(
                    text("ALTER TABLE metric_alerts ADD COLUMN maintenance_task_id INTEGER REFERENCES maintenance_tasks(id)")
                )
            if "inventory_item_id" not in existing_alert_columns:
                logger.info("Migration: ajout de la colonne metric_alerts.inventory_item_id")
                conn.execute(
                    text("ALTER TABLE metric_alerts ADD COLUMN inventory_item_id INTEGER REFERENCES inventory_items(id)")
                )
            if "acknowledged" not in existing_alert_columns:
                logger.info("Migration: ajout de la colonne metric_alerts.acknowledged")
                conn.execute(text("ALTER TABLE metric_alerts ADD COLUMN acknowledged BOOLEAN DEFAULT 0"))
            if "sensor_id" not in existing_alert_columns:
                logger.info("Migration: ajout de la colonne metric_alerts.sensor_id")
                conn.execute(text("ALTER TABLE metric_alerts ADD COLUMN sensor_id INTEGER REFERENCES sensors(id)"))
            if "notified" not in existing_alert_columns:
                logger.info("Migration: ajout de la colonne metric_alerts.notified")
                conn.execute(text("ALTER TABLE metric_alerts ADD COLUMN notified BOOLEAN NOT NULL DEFAULT 0"))

    if "icp_import_batches" in tables:
        existing_batch_columns = {col["name"] for col in inspector.get_columns("icp_import_batches")}
        if "pdf_filename" not in existing_batch_columns:
            logger.info("Migration: ajout de la colonne icp_import_batches.pdf_filename")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE icp_import_batches ADD COLUMN pdf_filename VARCHAR(255)"))

    if "fish_species" in tables:
        existing_fish_species_columns = {col["name"] for col in inspector.get_columns("fish_species")}
        if "water_type" not in existing_fish_species_columns:
            logger.info("Migration: ajout de la colonne fish_species.water_type")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE fish_species ADD COLUMN water_type VARCHAR(4) NOT NULL DEFAULT 'sea'"))

    if "equipments" in tables:
        if "max_duration_seconds" not in {col["name"] for col in inspector.get_columns("equipments")}:
            logger.info("Migration: ajout de la colonne equipments.max_duration_seconds")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE equipments ADD COLUMN max_duration_seconds INTEGER"))

    if "rules" in tables:
        if "revert_on_exit" not in {col["name"] for col in inspector.get_columns("rules")}:
            logger.info("Migration: ajout de la colonne rules.revert_on_exit")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE rules ADD COLUMN revert_on_exit BOOLEAN NOT NULL DEFAULT 0"))

    if "maintenance_tasks" in tables:
        existing_task_columns = {col["name"] for col in inspector.get_columns("maintenance_tasks")}
        if "reminder_sent_on" not in existing_task_columns:
            logger.info("Migration: ajout de la colonne maintenance_tasks.reminder_sent_on")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE maintenance_tasks ADD COLUMN reminder_sent_on DATE"))

    if "frags" in tables and "quantity" not in {c["name"] for c in inspector.get_columns("frags")}:
        # Boutures en lots : la fiche porte le nombre encore disponible
        logger.info("Migration: ajout de la colonne frags.quantity")
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE frags ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1"))
            conn.execute(text("UPDATE frags SET quantity = 0 WHERE status IN ('reserved', 'transferred', 'lost')"))
            conn.execute(text("UPDATE frags SET status = 'empty' WHERE status = 'lost'"))
    if "transfer_certificates" in tables and "location_id" not in {
        c["name"] for c in inspector.get_columns("transfer_certificates")
    }:
        # Lieu de vente des cessions (table sale_locations créée par create_all)
        logger.info("Migration: ajout de la colonne transfer_certificates.location_id")
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE transfer_certificates ADD COLUMN location_id INTEGER REFERENCES sale_locations(id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_transfer_certificates_location_id ON transfer_certificates (location_id)"))
    if "water_parameters" in tables and "trend_alerted_at" not in {
        c["name"] for c in inspector.get_columns("water_parameters")
    }:
        logger.info("Migration: ajout de la colonne water_parameters.trend_alerted_at")
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE water_parameters ADD COLUMN trend_alerted_at TIMESTAMP"))
    if "showcase_settings" in tables and "price_label" not in {c["name"] for c in inspector.get_columns("showcase_settings")}:
        logger.info("Migration: ajout de la colonne showcase_settings.price_label")
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE showcase_settings ADD COLUMN price_label VARCHAR(30) NOT NULL DEFAULT 'Participation'"))
    if "showcase_reservations" in tables and "link_id" not in {
        c["name"] for c in inspector.get_columns("showcase_reservations")
    }:
        # Réservation rattachée au lien de partage utilisé (table showcase_links créée par create_all)
        logger.info("Migration: ajout de la colonne showcase_reservations.link_id")
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE showcase_reservations ADD COLUMN link_id INTEGER REFERENCES showcase_links(id)"))
    for table, column, ddl in (
        # RGPD : mention d'information, durée de conservation, anonymisation
        ("seller_profile", "privacy_notice", "TEXT NOT NULL DEFAULT ''"),
        ("seller_profile", "buyer_retention_years", "INTEGER NOT NULL DEFAULT 5"),
        ("transfer_certificates", "privacy_notice", "TEXT NOT NULL DEFAULT ''"),
        ("transfer_certificates", "anonymized_at", "TIMESTAMP"),
    ):
        if table in tables and column not in {c["name"] for c in inspector.get_columns(table)}:
            logger.info("Migration: ajout de la colonne %s.%s", table, column)
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
    for table, column in (("corals", "acquired_from"), ("frags", "acquired_from"),
                          ("transfer_certificate_items", "mother_acquired_from")):
        # Provenance (où le corail a été acquis), jusqu'aux certificats de cession
        if table in tables and column not in {c["name"] for c in inspector.get_columns(table)}:
            logger.info("Migration: ajout de la colonne %s.%s", table, column)
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} VARCHAR(120)"))
    for table in ("fishes", "corals", "invertebrates", "plants"):
        # Quantité d'individus (1 par défaut : fiches existantes inchangées)
        if table in tables and "quantity" not in {c["name"] for c in inspector.get_columns(table)}:
            logger.info("Migration: ajout de la colonne %s.quantity", table)
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1"))
    if "io_modules" in tables and "number" not in {c["name"] for c in inspector.get_columns("io_modules")}:
        # Numéro affiché des modules d'extension (« Module 1 »...), par contrôleur, dans l'ordre de création
        logger.info("Migration: numérotation des modules d'extension")
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE io_modules ADD COLUMN number INTEGER NOT NULL DEFAULT 1"))
            conn.execute(text("""
                UPDATE io_modules SET number = (
                    SELECT COUNT(*) FROM io_modules other
                    WHERE other.controller_id = io_modules.controller_id AND other.id <= io_modules.id
                )
            """))
    if "io_modules" in tables and engine.dialect.name == "sqlite":
        # Type PCA9685 (sorties PWM) : la contrainte CHECK n'autorisait que les PCF
        with engine.connect() as conn:
            ddl = conn.execute(text("SELECT sql FROM sqlite_master WHERE name = 'io_modules'")).scalar() or ""
        if "PCA9685" not in ddl:
            logger.info("Migration: io_modules accepte les modules PCA9685")
            _rebuild_table_sqlite("io_modules")
    if "io_modules" in tables:
        # Adresses I2C en minuscules (0x20), comme le firmware et l'appli
        with engine.begin() as conn:
            conn.execute(text("UPDATE io_modules SET address = LOWER(address) WHERE address <> LOWER(address)"))
    if "purchase_documents" in tables and "cites_species" not in {c["name"] for c in inspector.get_columns("purchase_documents")}:
        logger.info("Migration: ajout de la colonne purchase_documents.cites_species")
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE purchase_documents ADD COLUMN cites_species TEXT NOT NULL DEFAULT '{}'"))
    if "sensors" in tables and "last_reading_at" not in {c["name"] for c in inspector.get_columns("sensors")}:
        logger.info("Migration: ajout de la colonne sensors.last_reading_at")
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE sensors ADD COLUMN last_reading_at TIMESTAMP"))
            if "sensors_reading" in tables:
                conn.execute(text("""
                    UPDATE sensors SET last_reading_at = (
                        SELECT MAX(r.timestamp) FROM sensors_reading r WHERE r.sensor_id = sensors.id
                    )
                """))
    for table in ("sensors", "equipments"):
        # Nom technique encore utilisé par le firmware flashé (transition après renommage)
        if table in tables and "deployed_technical_name" not in {c["name"] for c in inspector.get_columns(table)}:
            logger.info("Migration: ajout de la colonne %s.deployed_technical_name", table)
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN deployed_technical_name VARCHAR(30)"))
    for table in ("sensors", "equipments", "lights", "rules", "equipment_groups"):
        # Nom affiché unique par aquarium seulement (et plus dans toute l'installation)
        index_name = f"ix_{table}_name"
        if table in tables and any(i["name"] == index_name and i["unique"] for i in inspector.get_indexes(table)):
            logger.info("Migration: le nom de %s n'est plus unique globalement", table)
            with engine.begin() as conn:
                conn.execute(text(f"DROP INDEX {index_name}"))
                conn.execute(text(f"CREATE INDEX {index_name} ON {table} (name)"))
    for table in ("fish_species", "coral_species", "plant_species", "invertebrate_species"):
        # Catalogue identifié par le nom commun : plusieurs variétés d'une même
        # espèce (ex. Euphyllia paraancora « marteau » et « gold »)
        index_name = f"ix_{table}_scientific_name"
        if table in tables and any(i["name"] == index_name and i["unique"] for i in inspector.get_indexes(table)):
            logger.info("Migration: le nom scientifique de %s n'est plus unique", table)
            with engine.begin() as conn:
                conn.execute(text(f"DROP INDEX {index_name}"))
                conn.execute(text(f"CREATE INDEX {index_name} ON {table} (scientific_name)"))
        # Fiche du catalogue commun modifiée localement : épargnée par la synchronisation
        if table in tables and "customized" not in {c["name"] for c in inspector.get_columns(table)}:
            logger.info("Migration: ajout de la colonne %s.customized", table)
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN customized BOOLEAN NOT NULL DEFAULT 0"))
    if "frags" in tables and "showcase_hidden" not in {c["name"] for c in inspector.get_columns("frags")}:
        logger.info("Migration: ajout de la colonne frags.showcase_hidden")
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE frags ADD COLUMN showcase_hidden BOOLEAN NOT NULL DEFAULT 0"))
    if "transfer_certificates" in tables and "payment_method" in {
        c["name"] for c in inspector.get_columns("transfer_certificates")
    }:
        # Règlement retiré : les boutures servent à la traçabilité, pas à la vente
        logger.info("Migration: suppression de la colonne transfer_certificates.payment_method")
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE transfer_certificates DROP COLUMN payment_method"))
    if "transfer_certificate_items" in tables and "quantity" not in {
        c["name"] for c in inspector.get_columns("transfer_certificate_items")
    }:
        logger.info("Migration: ajout de la colonne transfer_certificate_items.quantity")
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE transfer_certificate_items ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1"))

    if "inventory_items" in tables and "opened_on" not in {c["name"] for c in inspector.get_columns("inventory_items")}:
        logger.info("Migration: ajout de la colonne inventory_items.opened_on")
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE inventory_items ADD COLUMN opened_on DATE"))

    for scoped_table in ("inventory_items", "maintenance_tasks"):
        if scoped_table in tables:
            scoped_columns = {col["name"] for col in inspector.get_columns(scoped_table)}
            if "scope" not in scoped_columns:
                # Portée des tâches et du stock : un aquarium, plusieurs ou tous
                logger.info(f"Migration: ajout de la colonne {scoped_table}.scope")
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {scoped_table} ADD COLUMN scope VARCHAR(10) NOT NULL DEFAULT 'single'"))

    if "sensors_reading" in tables:
        existing_reading_indexes = {ix["name"] for ix in inspector.get_indexes("sensors_reading")}
        if "ix_sensors_reading_sensor_ts" not in existing_reading_indexes:
            # Historique des capteurs (graphiques 24 h / 7 j / 30 j) : lecture par capteur et période
            logger.info("Migration: index sensors_reading(sensor_id, timestamp)")
            with engine.begin() as conn:
                conn.execute(
                    text("CREATE INDEX IF NOT EXISTS ix_sensors_reading_sensor_ts ON sensors_reading (sensor_id, timestamp)")
                )

    if "controllers" in tables:
        existing_controller_columns = {col["name"] for col in inspector.get_columns("controllers")}
        if "rtc_model" not in existing_controller_columns:
            logger.info("Migration: ajout de la colonne controllers.rtc_model")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE controllers ADD COLUMN rtc_model VARCHAR(10)"))
        if "i2c_frequency_khz" not in existing_controller_columns:
            logger.info("Migration: ajout de la colonne controllers.i2c_frequency_khz")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE controllers ADD COLUMN i2c_frequency_khz INTEGER NOT NULL DEFAULT 50"))

    if "lights" in tables:
        existing_light_columns = {col["name"] for col in inspector.get_columns("lights")}
        with engine.begin() as conn:
            for column, ddl in (
                ("pwm_frequency", "INTEGER NOT NULL DEFAULT 1000"),
                ("moonlight_channel_id", "INTEGER"),
                ("moonlight_intensity", "INTEGER NOT NULL DEFAULT 0"),
                ("acclimation_start", "DATE"),
                ("acclimation_days", "INTEGER"),
                ("acclimation_start_percent", "INTEGER NOT NULL DEFAULT 50"),
            ):
                if column not in existing_light_columns:
                    logger.info("Migration: ajout de la colonne lights.%s", column)
                    conn.execute(text(f"ALTER TABLE lights ADD COLUMN {column} {ddl}"))

    if "aquariums" in tables:
        existing_aquarium_columns = {col["name"] for col in inspector.get_columns("aquariums")}
        with engine.begin() as conn:
            for column, ddl in (
                ("maintenance_until", "TIMESTAMP"),
                ("maintenance_started_at", "TIMESTAMP"),
                ("maintenance_equipment_ids", "JSON"),
                ("maintenance_saved_modes", "JSON"),
            ):
                if column not in existing_aquarium_columns:
                    logger.info("Migration: ajout de la colonne aquariums.%s", column)
                    conn.execute(text(f"ALTER TABLE aquariums ADD COLUMN {column} {ddl}"))

    if "dosing_products" in tables:
        existing_dosing_columns = {col["name"] for col in inspector.get_columns("dosing_products")}
        with engine.begin() as conn:
            for column, ddl in (("concentration", "FLOAT"), ("concentration_unit", "VARCHAR(10)"), ("brand", "VARCHAR(60)")):
                if column not in existing_dosing_columns:
                    logger.info("Migration: ajout de la colonne dosing_products.%s", column)
                    conn.execute(text(f"ALTER TABLE dosing_products ADD COLUMN {column} {ddl}"))

    if "lights_channels" in tables:
        existing_channel_columns = {col["name"] for col in inspector.get_columns("lights_channels")}
        with engine.begin() as conn:
            for column, ddl in (
                ("spectrum", "VARCHAR(20) NOT NULL DEFAULT 'other'"),
                ("inverted", "BOOLEAN NOT NULL DEFAULT 0"),
                ("moonlight_intensity", "INTEGER NOT NULL DEFAULT 0"),
                ("min_intensity", "INTEGER NOT NULL DEFAULT 0"),
            ):
                if column not in existing_channel_columns:
                    logger.info("Migration: ajout de la colonne lights_channels.%s", column)
                    conn.execute(text(f"ALTER TABLE lights_channels ADD COLUMN {column} {ddl}"))
            # Anciennes couleurs nommées (BLEU, UV...) -> hexadécimal ; plafond 0 -> 100 %
            conn.execute(text("UPDATE lights_channels SET color = '#ffffff' WHERE color NOT LIKE '#%'"))
            conn.execute(text("UPDATE lights_channels SET max_intensity = 100 WHERE max_intensity = 0"))

    if "sensors" in tables:
        existing_sensor_columns = {col["name"] for col in inspector.get_columns("sensors")}
        with engine.begin() as conn:
            if "address" not in existing_sensor_columns:
                logger.info("Migration: ajout de la colonne sensors.address")
                conn.execute(text("ALTER TABLE sensors ADD COLUMN address VARCHAR(30)"))
            if "interval" not in existing_sensor_columns:
                logger.info("Migration: ajout de la colonne sensors.interval")
                conn.execute(text("ALTER TABLE sensors ADD COLUMN interval INTEGER"))

        # La contrainte unique (controller_id, pin_id) empêchait plusieurs
        # sondes 1-Wire (ex: DS18B20) de partager la même broche. SQLite ne
        # sait pas "DROP CONSTRAINT" directement : on reconstruit la table
        # sans elle, en copiant les données telles quelles (même id, donc
        # les FK d'autres tables vers sensors.id restent valides).
        if engine.dialect.name == "sqlite":
            _repair_failed_sensors_rebuild()
            has_old_pin_constraint = any(
                set(uc["column_names"]) == {"controller_id", "pin_id"}
                for uc in inspect(engine).get_unique_constraints("sensors")
            )
            if has_old_pin_constraint:
                logger.info("Migration: reconstruction de sensors sans la contrainte unique (controller_id, pin_id)")
                _rebuild_sensors_table_sqlite()


def _run_sqlite_transaction(statements: list[str]) -> None:
    # pysqlite n'ouvre pas de transaction pour le DDL (chaque ALTER/CREATE est
    # auto-commité) : BEGIN explicite pour que tout soit annulé en cas d'échec.
    raw = engine.raw_connection()
    dbapi_conn = raw.driver_connection
    previous_isolation = dbapi_conn.isolation_level
    dbapi_conn.isolation_level = None
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("BEGIN")
        for statement in statements:
            cursor.execute(statement)
        cursor.execute("COMMIT")
    except Exception:
        cursor.execute("ROLLBACK")
        raise
    finally:
        dbapi_conn.isolation_level = previous_isolation
        raw.close()


def _rebuild_table_sqlite(name: str) -> None:
    # Procédure officielle SQLite (create new / copy / drop / rename) : un
    # RENAME de l'ancienne table réécrirait les FK des autres tables
    # (sensors_reading, rule_conditions...) vers le nom temporaire.
    table = Base.metadata.tables[name]
    create_sql = str(CreateTable(table).compile(engine)).strip()
    create_new_sql = create_sql.replace(f"CREATE TABLE {name} (", f"CREATE TABLE {name}_new (", 1)
    assert create_new_sql != create_sql
    columns = ", ".join(c.name for c in table.columns)
    _run_sqlite_transaction([
        f"DROP TABLE IF EXISTS {name}_new",
        create_new_sql,
        f"INSERT INTO {name}_new ({columns}) SELECT {columns} FROM {name}",
        f"DROP TABLE {name}",
        f"ALTER TABLE {name}_new RENAME TO {name}",
        *(str(CreateIndex(index).compile(engine)) for index in table.indexes),
    ])


def _rebuild_sensors_table_sqlite() -> None:
    _rebuild_table_sqlite("sensors")


def _repair_failed_sensors_rebuild() -> None:
    # Une première version de la migration a pu laisser les données dans
    # sensors_old (et les FK des autres tables pointant dessus). Renommer
    # sensors_old -> sensors rétablit l'état d'origine (SQLite réécrit les
    # FK), la reconstruction correcte est ensuite rejouée.
    with engine.connect() as conn:
        if not inspect(conn).has_table("sensors_old"):
            return
        new_count = conn.execute(text("SELECT COUNT(*) FROM sensors")).scalar()
    if new_count:
        logger.error("Migration: sensors_old et sensors contiennent des données, réparation manuelle nécessaire")
        return
    logger.warning("Migration: restauration de sensors depuis sensors_old (reconstruction précédente incomplète)")
    _run_sqlite_transaction([
        "DROP TABLE sensors",
        "ALTER TABLE sensors_old RENAME TO sensors",
    ])


def _seed_default_admin():
    """
    Crée un compte admin par défaut si la base ne contient encore aucun
    utilisateur (premier démarrage). Le mot de passe généré doit être changé
    dès la première connexion (must_change_password=True).
    """
    db = SessionLocal()
    try:
        if db.query(User).first() is not None:
            return

        logger.warning(
            "Aucun utilisateur en base : création du compte admin par défaut '%s'. "
            "Changez son mot de passe dès la première connexion.",
            settings.default_admin_username,
        )
        hashed_pw = bcrypt.hashpw(settings.default_admin_password.encode("utf-8"), bcrypt.gensalt())
        admin = User(
            username=settings.default_admin_username,
            password=hashed_pw.decode("utf-8"),
            role=UserRole.admin,
            must_change_password=True,
        )
        db.add(admin)
        db.commit()
    finally:
        db.close()


_apply_lightweight_migrations()


def _apply_data_migrations():
    """
    Conversions de données à faire une seule fois (table schema_migrations).
    """
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (name VARCHAR(100) PRIMARY KEY, applied_at TIMESTAMP)"))
        tables = inspect(conn).get_table_names()
        name = "rule_states_logical"
        if conn.execute(text("SELECT 1 FROM schema_migrations WHERE name = :n"), {"n": name}).first() is None:
            # Les règles sur un capteur inversé étaient saisies en état brut de la
            # broche (LOW = plein pour un flotteur inversé) ; elles s'expriment
            # désormais comme l'affichage. On inverse l'état enregistré : le
            # firmware généré reste identique, le comportement aussi.
            if "rule_conditions" in tables and "sensors" in tables:
                changed = conn.execute(text("""
                    UPDATE rule_conditions SET trigger_state = CASE UPPER(trigger_state)
                        WHEN 'LOW' THEN 'HIGH' WHEN 'HIGH' THEN 'LOW'
                        WHEN 'ON' THEN 'OFF' WHEN 'OFF' THEN 'ON' ELSE trigger_state END
                    WHERE trigger_state IS NOT NULL
                      AND sensor_id IN (SELECT id FROM sensors WHERE is_inverted = 1)
                """)).rowcount
                logger.info("Migration: %d condition(s) de règle converties en état logique (capteurs inversés)", changed)
            conn.execute(text("INSERT INTO schema_migrations (name, applied_at) VALUES (:n, CURRENT_TIMESTAMP)"), {"n": name})
        name = "dashboard_water_trend_card"
        if conn.execute(text("SELECT 1 FROM schema_migrations WHERE name = :n"), {"n": name}).first() is None:
            # L'évolution des paramètres était un bloc fixe en haut du tableau de
            # bord : elle devient une carte (déplaçable, redimensionnable), en tête.
            if "dashboard_cards" in tables and "aquariums" in tables:
                added = conn.execute(text("""
                    INSERT INTO dashboard_cards (aquarium_id, title, type, icon, col_span, position, created_at)
                    SELECT a.id, 'water_trend', 'water_trend', 'show_chart', 12, 0, CURRENT_TIMESTAMP FROM aquariums a
                    WHERE NOT EXISTS (SELECT 1 FROM dashboard_cards c WHERE c.aquarium_id = a.id AND c.type = 'water_trend')
                """)).rowcount
                logger.info("Migration: carte d'évolution des paramètres ajoutée à %d aquarium(s)", added)
            conn.execute(text("INSERT INTO schema_migrations (name, applied_at) VALUES (:n, CURRENT_TIMESTAMP)"), {"n": name})
        name = "inventory_round_quantities"
        if conn.execute(text("SELECT 1 FROM schema_migrations WHERE name = :n"), {"n": name}).first() is None:
            # Quantités du stock faussées par l'addition de décimaux (12.199999999999 au lieu de 12,2)
            if "inventory_items" in tables:
                conn.execute(text("UPDATE inventory_items SET quantity = ROUND(quantity, 6)"))
            conn.execute(text("INSERT INTO schema_migrations (name, applied_at) VALUES (:n, CURRENT_TIMESTAMP)"), {"n": name})
        name = "controller_status_uppercase"
        if conn.execute(text("SELECT 1 FROM schema_migrations WHERE name = :n"), {"n": name}).first() is None:
            # « offline » publié par ESPHome à l'arrêt propre, enregistré tel quel : liste des contrôleurs en erreur
            if "controllers" in tables:
                conn.execute(text("UPDATE controllers SET status = UPPER(status) WHERE status IN ('online', 'offline')"))
            conn.execute(text("INSERT INTO schema_migrations (name, applied_at) VALUES (:n, CURRENT_TIMESTAMP)"), {"n": name})
        name = "catalog_resync_adopt_local"
        if conn.execute(text("SELECT 1 FROM schema_migrations WHERE name = :n"), {"n": name}).first() is None:
            # Fiches locales homonymes désormais rattachées au catalogue commun : sans ETag, la
            # prochaine synchronisation réapplique tout le catalogue au lieu de recevoir « 304 »
            if "catalog_sync_state" in tables:
                conn.execute(text("UPDATE catalog_sync_state SET etag = NULL"))
            conn.execute(text("INSERT INTO schema_migrations (name, applied_at) VALUES (:n, CURRENT_TIMESTAMP)"), {"n": name})
        name = "moonlight_per_channel"
        if conn.execute(text("SELECT 1 FROM schema_migrations WHERE name = :n"), {"n": name}).first() is None:
            # Clair de lune : un seul canal par lampe -> une intensité par canal
            if "lights" in tables and "lights_channels" in tables:
                moved = conn.execute(text("""
                    UPDATE lights_channels SET moonlight_intensity = (
                        SELECT l.moonlight_intensity FROM lights l
                        WHERE l.id = lights_channels.light_id AND l.moonlight_channel_id = lights_channels.id)
                    WHERE id IN (SELECT moonlight_channel_id FROM lights WHERE moonlight_channel_id IS NOT NULL)
                """)).rowcount
                logger.info("Migration: clair de lune repris sur %d canal(aux)", moved)
            conn.execute(text("INSERT INTO schema_migrations (name, applied_at) VALUES (:n, CURRENT_TIMESTAMP)"), {"n": name})
        name = "coral_light_par50"
        if conn.execute(text("SELECT 1 FROM schema_migrations WHERE name = :n"), {"n": name}).first() is None:
            # Lumière des coraux : paliers de 100 PAR sur 1-10 → paliers de 50 PAR
            # sur 1-15. Même lumière = niveau doublé, plafonné à 15 (750 PAR).
            if "coral_species" in tables:
                changed = conn.execute(text("""
                    UPDATE coral_species SET light_min = MIN(light_min * 2, 15), light_max = MIN(light_max * 2, 15)
                """)).rowcount
                logger.info("Migration: lumière de %d espèce(s) de corail convertie en paliers de 50 PAR", changed)
            if "corals" in tables:
                changed = conn.execute(text("""
                    UPDATE corals SET light_range = json_object(
                        'min', MIN(CAST(json_extract(light_range, '$.min') AS INTEGER) * 2, 15),
                        'max', MIN(CAST(json_extract(light_range, '$.max') AS INTEGER) * 2, 15))
                    WHERE light_range IS NOT NULL AND json_valid(light_range)
                """)).rowcount
                logger.info("Migration: lumière de %d corail(aux) convertie en paliers de 50 PAR", changed)
            conn.execute(text("INSERT INTO schema_migrations (name, applied_at) VALUES (:n, CURRENT_TIMESTAMP)"), {"n": name})


_apply_data_migrations()


def _backfill_frag_movements():
    from services.frags import backfill_movements

    db = SessionLocal()
    try:
        count = backfill_movements(db)
        if count:
            logger.info("Migration: historique reconstitué pour %d lot(s) de boutures", count)
    finally:
        db.close()


_backfill_frag_movements()
purge_idempotency_keys()
_seed_default_admin()


def _seed_species():
    db = SessionLocal()
    try:
        seed_species_catalog(db)
    finally:
        db.close()


_seed_species()


def _mark_customized_species_once():
    """Avant la première synchronisation du catalogue commun : les fiches du jeu
    de départ déjà modifiées ici sont marquées « customized » (jamais écrasées)."""
    name = "species_customized_detect"
    with engine.begin() as conn:
        if conn.execute(text("SELECT 1 FROM schema_migrations WHERE name = :n"), {"n": name}).first() is not None:
            return
    db = SessionLocal()
    try:
        marked = mark_customized_builtins(db)
        logger.info("Migration: %d fiche(s) du catalogue modifiée(s) localement, protégée(s) de la synchronisation", marked)
    finally:
        db.close()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO schema_migrations (name, applied_at) VALUES (:n, CURRENT_TIMESTAMP)"), {"n": name})


_mark_customized_species_once()


def _technical_names_with_aquarium_once():
    """Noms techniques « <nom>_<aquarium> » (ex. osmolateur_recif au lieu de
    osmolateur_2). Le firmware flashé garde l'ancien nom jusqu'au prochain flash
    (deployed_technical_name) : capteurs et commandes continuent de fonctionner."""
    name = "technical_names_with_aquarium"
    with engine.begin() as conn:
        if conn.execute(text("SELECT 1 FROM schema_migrations WHERE name = :n"), {"n": name}).first() is not None:
            return
    from models.controller import Controller
    from models.equipment import Equipment
    from models.sensor import Sensor
    from services import technical_names

    db = SessionLocal()
    try:
        renamed, controllers = 0, set()
        for model, kind in ((Equipment, "equipment"), (Sensor, "sensor")):
            for entity in db.query(model).order_by(model.id).all():
                if technical_names.rename(db, entity, kind):
                    renamed += 1
                    controllers.add(entity.controller_id)
                    db.flush()
        if controllers:
            db.query(Controller).filter(Controller.id.in_(controllers)).update(
                {Controller.is_dirty: True}, synchronize_session=False
            )
        db.commit()
        logger.info("Migration: %d nom(s) technique(s) avec l'aquarium, %d contrôleur(s) à reflasher", renamed, len(controllers))
    finally:
        db.close()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO schema_migrations (name, applied_at) VALUES (:n, CURRENT_TIMESTAMP)"), {"n": name})


_technical_names_with_aquarium_once()


def _cites_links_backfill_once():
    """Une fois : coraux et documents d'achat existants qui partagent un numéro CITES liés."""
    name = "cites_links_backfill"
    with engine.begin() as conn:
        if conn.execute(text("SELECT 1 FROM schema_migrations WHERE name = :n"), {"n": name}).first() is not None:
            return
    from models.purchase_document import PurchaseDocument
    from services.cites_links import link_corals_to_document, split_numbers

    db = SessionLocal()
    try:
        linked = sum(
            link_corals_to_document(db, document, split_numbers(document.cites_number))
            for document in db.query(PurchaseDocument).filter(PurchaseDocument.cites_number != "")
        )
        db.commit()
        if linked:
            logger.info("Migration: %d corail(aux) lié(s) à leurs documents d'achat par numéro CITES", linked)
    finally:
        db.close()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO schema_migrations (name, applied_at) VALUES (:n, CURRENT_TIMESTAMP)"), {"n": name})


_cites_links_backfill_once()

logger.info("Démarrage de AquasManagerAPI...")
if settings.debug:
    logging.info("Mode debug activé.")


async def periodic_log_purge_task():
    """Vérifie et purge les logs toutes les 24 heures en arrière-plan."""
    while True:
        # Attend 24 heures avant chaque exécution (24 * 3600 secondes)
        await asyncio.sleep(86400)
        try:
            logger.info("Lancement de la tâche automatique de purge des logs...")
            purge_old_logs(db_path=settings.database.sqlite_path, retention_days=settings.log_day_retention, run_vacuum=True)
        except Exception as e:
            logger.error(f"Erreur dans la tâche de purge automatique : {e}")


async def periodic_backup_purge_task():
    """Sauvegarde automatique (créneau vérifié chaque minute) et purge quotidienne."""
    last_purge = time.monotonic()
    while True:
        await asyncio.sleep(60)
        try:
            # Thread dédié : compression et copie éventuelle vers un partage réseau
            await asyncio.to_thread(run_scheduled_backup_if_due)
        except Exception:
            logger.exception("Erreur de la sauvegarde automatique")
        if time.monotonic() - last_purge >= 86400:
            last_purge = time.monotonic()
            try:
                logger.info("Lancement de la tâche automatique de purge des backups...")
                purge_old_backups(retention_days=settings.backup_retention_days)
            except Exception as e:
                logger.error(f"Erreur dans la purge automatique des backups : {e}")


def _anonymize_expired_buyers() -> None:
    """RGPD : acquéreurs des cessions plus anciennes que la durée de conservation choisie."""
    db = SessionLocal()
    try:
        anonymize_expired(db, get_seller_profile(db))
    except Exception:
        logger.exception("Erreur lors de l'anonymisation des acquéreurs")
    finally:
        db.close()


async def periodic_activation_purge_task():
    """Purge l'historique d'activation des équipements toutes les 24 heures."""
    while True:
        await asyncio.sleep(86400)
        db = SessionLocal()
        try:
            logger.info("Lancement de la tâche automatique de purge des activations...")
            EquipmentService.purge_old_activations(db, retention_days=settings.activation_retention_days)
        except Exception as e:
            logger.error(f"Erreur dans la purge automatique des activations : {e}")
        finally:
            db.close()
        _anonymize_expired_buyers()


def _expire_maintenance_once():
    db = SessionLocal()
    try:
        maintenance.expire_due(db)
    finally:
        db.close()


def _clear_silent_probes_once():
    db = SessionLocal()
    try:
        clear_silent_probes(db, notify=mqtt.mqtt_driver._broadcast_to_ws)
    finally:
        db.close()


async def periodic_silent_probe_task():
    """Chaque minute : sondes muettes → « Pas de mesure » ; fin des maintenances arrivées à échéance."""
    while True:
        await asyncio.sleep(60)
        try:
            await asyncio.to_thread(_clear_silent_probes_once)
            # Fin des maintenances arrivées à échéance (équipements remis)
            await asyncio.to_thread(_expire_maintenance_once)
        except Exception as e:
            logger.error(f"Erreur dans la vérification des sondes muettes : {e}")


async def periodic_metric_alert_task():
    """Réévalue toutes les 5 minutes les paramètres d'eau et capteurs ciblés
    pour ouvrir/fermer les MetricAlert correspondantes."""
    while True:
        await asyncio.sleep(300)
        try:
            # Thread dédié : l'évaluation envoie des notifications (HTTP bloquant)
            await asyncio.to_thread(_evaluate_metric_alerts_once)
        except Exception as e:
            logger.error(f"Erreur dans l'évaluation périodique des alertes : {e}")


def _evaluate_metric_alerts_once():
    db = SessionLocal()
    try:
        evaluate_metric_alerts(db)
        send_due_today_reminders(db)
        check_service_due(db)
        check_trend_alerts(db)
    finally:
        db.close()


async def periodic_alert_purge_task():
    """Purge les alertes résolues (métriques + défauts équipement) toutes
    les 24 heures, comme pour les logs/backups/activations."""
    while True:
        await asyncio.sleep(86400)
        db = SessionLocal()
        try:
            logger.info("Lancement de la tâche automatique de purge des alertes...")
            purge_old_metric_alerts(db, retention_days=settings.alert_retention_days)
            purge_old_faults(db, retention_days=settings.alert_retention_days)
            purge_expired_refresh_tokens(db)
            purge_old_audit_logs(db, retention_days=settings.audit_retention_days)
            purge_old_sensor_readings(db, retention_days=settings.sensor_reading_retention_days)
        except Exception as e:
            logger.error(f"Erreur dans la purge automatique des alertes : {e}")
        finally:
            db.close()


def _group_orders_once():
    from services.group_orders import check_news

    db = SessionLocal()
    try:
        check_news(db)
    finally:
        db.close()


async def periodic_group_orders_task():
    """Commandes groupées : nouvelles annonces du secteur et nouveaux participants, chaque heure."""
    await asyncio.sleep(120)
    while True:
        try:
            await asyncio.to_thread(_group_orders_once)
        except Exception as e:
            logger.warning(f"Commandes groupées : vérification impossible ({e})")
        await asyncio.sleep(3600)


def _sync_catalog_once():
    db = SessionLocal()
    try:
        sync_catalog(db)
    finally:
        db.close()


async def periodic_catalog_sync_task():
    """Catalogue commun d'espèces : une minute après le démarrage, puis toutes
    les catalog_sync_hours heures (sans effet si le catalogue n'a pas changé)."""
    await asyncio.sleep(60)
    while True:
        try:
            await asyncio.to_thread(_sync_catalog_once)
        except Exception as e:
            logger.error(f"Erreur dans la synchronisation du catalogue : {e}")
        await asyncio.sleep(max(1, settings.catalog_sync_hours) * 3600)


async def periodic_demo_task(app: FastAPI):
    """Démo : une mesure simulée par sonde chaque minute, remise à zéro chaque nuit."""
    next_reset = time.monotonic() + demo.seconds_until_reset()
    while True:
        await asyncio.sleep(60)
        try:
            if time.monotonic() >= next_reset:
                await asyncio.to_thread(demo.reset_demo, app)
                next_reset = time.monotonic() + demo.seconds_until_reset()
            await asyncio.to_thread(demo.simulate_sensors, mqtt.mqtt_driver)
        except Exception:
            logger.exception("Démo : erreur de la tâche périodique")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- AU DÉMARRAGE ---
    mqtt.mqtt_driver.main_loop = asyncio.get_running_loop()
    demo_task = None
    if settings.demo:
        # Démo : pas de broker ; données recréées à chaque démarrage puis chaque nuit
        await asyncio.to_thread(demo.reset_demo, app)
        demo_task = asyncio.create_task(periodic_demo_task(app))
    else:
        logger.info("Connexion au broker MQTT...")
        mqtt.mqtt_driver.connect()  # On connecte l'unique instance

    # 1. Purge immédiate au lancement des logs
    try:
        logger.info("Exécution de la purge initiale des logs...")
        purge_old_logs(db_path=settings.database.sqlite_path, retention_days=settings.log_day_retention, run_vacuum=True)
    except Exception as e:
        logger.error(f"Erreur lors de la purge au démarrage : {e}")

    # 2. Lancement de la tâche de fond quotidienne pour les logs
    purge_task = asyncio.create_task(periodic_log_purge_task())

    # 3. Purge immédiate au lancement des backups, puis tâche de fond quotidienne
    try:
        logger.info("Exécution de la purge initiale des backups...")
        purge_old_backups(retention_days=settings.backup_retention_days)
    except Exception as e:
        logger.error(f"Erreur lors de la purge des backups au démarrage : {e}")

    backup_purge_task = asyncio.create_task(periodic_backup_purge_task())

    # 4. Purge immédiate au lancement des activations, puis tâche de fond quotidienne
    db = SessionLocal()
    try:
        logger.info("Exécution de la purge initiale des activations...")
        EquipmentService.purge_old_activations(db, retention_days=settings.activation_retention_days)
    except Exception as e:
        logger.error(f"Erreur lors de la purge des activations au démarrage : {e}")
    finally:
        db.close()

    _anonymize_expired_buyers()
    activation_purge_task = asyncio.create_task(periodic_activation_purge_task())

    # 5. Évaluation immédiate des alertes au lancement, puis tâche de fond toutes les 5 minutes
    try:
        logger.info("Exécution de l'évaluation initiale des alertes...")
        await asyncio.to_thread(_evaluate_metric_alerts_once)
    except Exception as e:
        logger.error(f"Erreur lors de l'évaluation des alertes au démarrage : {e}")

    metric_alert_task = asyncio.create_task(periodic_metric_alert_task())
    silent_probe_task = asyncio.create_task(periodic_silent_probe_task())

    # 6. Purge immédiate des alertes résolues au lancement, puis tâche de fond quotidienne
    db = SessionLocal()
    try:
        logger.info("Exécution de la purge initiale des alertes...")
        purge_old_metric_alerts(db, retention_days=settings.alert_retention_days)
        purge_old_faults(db, retention_days=settings.alert_retention_days)
        purge_expired_refresh_tokens(db)
        purge_old_audit_logs(db, retention_days=settings.audit_retention_days)
        purge_old_sensor_readings(db, retention_days=settings.sensor_reading_retention_days)
    except Exception as e:
        logger.error(f"Erreur lors de la purge des alertes au démarrage : {e}")
    finally:
        db.close()

    alert_purge_task = asyncio.create_task(periodic_alert_purge_task())

    # 7. Catalogue commun d'espèces (hub de l'éditeur)
    catalog_task = asyncio.create_task(periodic_catalog_sync_task()) if sync_enabled() else None
    # Commandes groupées (hub de l'éditeur), sauf sur la démo publique
    group_orders_task = asyncio.create_task(periodic_group_orders_task()) if sync_enabled() and not settings.demo else None

    yield  # Ici, l'application tourne

    if demo_task:
        demo_task.cancel()

    # --- À LA FERMETURE ---
    purge_task.cancel()
    backup_purge_task.cancel()
    activation_purge_task.cancel()
    metric_alert_task.cancel()
    silent_probe_task.cancel()
    alert_purge_task.cancel()
    if catalog_task:
        catalog_task.cancel()
    if group_orders_task:
        group_orders_task.cancel()
    try:
        await purge_task
    except asyncio.CancelledError:
        pass
    try:
        await backup_purge_task
    except asyncio.CancelledError:
        pass
    try:
        await activation_purge_task
    except asyncio.CancelledError:
        pass
    try:
        await metric_alert_task
    except asyncio.CancelledError:
        pass
    try:
        await alert_purge_task
    except asyncio.CancelledError:
        pass

    logger.info("Déconnexion du broker MQTT")
    mqtt.mqtt_driver.client.loop_stop()
    mqtt.mqtt_driver.client.disconnect()

app = FastAPI(
    title="AquasManager API",
    version=__version__,
    root_path=settings.root_path,
    default_response_class=UTCJSONResponse,
    # Documentation servie par fastapi_swagger (patch_fastapi plus bas), sans les pages par défaut
    docs_url=None,
    redoc_url=None,
    swagger_ui_oauth2_redirect_url=None,
    lifespan=lifespan
)

# Code de fermeture : jeton absent, invalide ou expiré (le client le renouvelle puis se reconnecte)
WS_UNAUTHORIZED = 4401


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    États en direct (capteurs, équipements, contrôleurs) réservés aux comptes
    connectés : le premier message doit être {"type": "auth", "token": "<jeton>"}
    (pas de jeton dans l'URL : il finirait dans les journaux d'accès).
    """
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        verify_access_token(str(json.loads(first).get("token") or ""))
    except (asyncio.TimeoutError, ValueError, AttributeError, HTTPException, WebSocketDisconnect):
        try:
            await websocket.close(code=WS_UNAUTHORIZED)
        except RuntimeError:
            pass
        return
    ws_manager.register(websocket)
    try:
        while True:
            # Reçoit les pings du client pour maintenir la connexion active
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

patch_fastapi(app)


@app.get("/health", tags=["system"], include_in_schema=False)
def health():
    """Sonde de vie (installation Docker, supervision)."""
    return {"status": "ok"}

app.add_middleware(LogContextMiddleware)
app.add_middleware(AuditMiddleware)
# Après l'audit (donc autour) : une requête rejouée n'est ni refaite ni journalisée deux fois
app.add_middleware(IdempotencyMiddleware)

if settings.demo:
    # Avant CORS (donc à l'intérieur) : les refus gardent les en-têtes CORS
    app.add_middleware(demo.DemoGuardMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_urls,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

include_routes(app)