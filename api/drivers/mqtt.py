"""
Pilote MQTT : lien entre l'API et les contrôleurs ESP32 (firmware ESPHome).

Reçoit les états publiés par les contrôleurs (statut en ligne, état et mode
des équipements, défauts, mesures des capteurs, état des lampes, journaux),
les enregistre et les relaie à l'interface par WebSocket ; publie les
commandes (marche/arrêt, mode, programme des lampes). Une seule instance,
mqtt_driver, partagée par toute l'API.
"""

import asyncio
import json
import logging
import math
from datetime import datetime
from typing import Optional, Tuple

import paho.mqtt.client as mqtt

from middleware.database import SessionLocal
from models import Controller, Equipment, LogModel, Sensor, SensorReading
from models.equipment_activation import EquipmentActivation
from models.fault import EquipmentFault
from services import notify
from services.equipment import EquipmentService
from services.equipment_usage import record_runtime
from services.technical_names import firmware_name_column
from services.websocket import ws_manager
from settings import settings

# Codes de défaut osmolateur qui indiquent une vraie anomalie interne
# (nécessitent un acquittement manuel côté app, cf esphome_generator.py) par
# opposition aux interlocks capteurs qui se relâchent seuls.
LATCHED_FAULT_CODES = {"LEVEL_TIMEOUT", "TOO_MANY_CYCLES"}


class MQTTDriver:
    def __init__(self):
        # client_id doit être unique par environnement : deux clients MQTT
        # connectés avec le même client_id se font mutuellement déconnecter
        # par le broker à chaque (re)connexion (comportement standard du
        # protocole MQTT), ce qui provoquait une boucle de reconnexion
        # infinie dès que prod et recette étaient actifs en même temps sur
        # le même broker.
        self.client = mqtt.Client(client_id=f"AquasManagerAPI-{settings.env}")
        self.topic_prefix = settings.mqtt.topic_prefix
        self.db_session_factory = SessionLocal
        self.discovery_future: Optional[asyncio.Future] = None
        self.main_loop: Optional[asyncio.AbstractEventLoop] = None

    def _clear_stale_retained(self, db, topic_parts: list[str], msg) -> bool:
        """
        Le broker garde le dernier état publié (retained) sur chaque topic, même
        quand plus aucun firmware ne l'utilise : après un renommage reflashé
        (osmolateur -> osmolateur_recif) ou une suppression, l'ancien topic est
        renvoyé à chaque connexion de l'API. S'il désigne un contrôleur de cette
        installation mais aucun équipement ou capteur connu du firmware actuel
        (nom technique ou nom encore flashé), on l'efface en publiant un message
        vide conservé. Retourne True si le message a été effacé.
        """
        if len(topic_parts) != 5 or topic_parts[0] != self.topic_prefix or not msg.payload:
            return False
        _, controller_name, component, name, kind = topic_parts
        if component == "switch" and kind in ("state", "mode", "fault"):
            model = Equipment
        elif component in ("sensor", "binary_sensor") and kind == "state":
            model = Sensor
        else:
            return False
        # Seulement les contrôleurs de cette installation (le broker peut être partagé)
        if db.query(Controller.id).filter(Controller.technical_name == controller_name).first() is None:
            return False
        if db.query(model.id).filter(firmware_name_column(model) == name).first() is not None:
            return False
        self.client.publish(msg.topic, b"", qos=1, retain=True)
        logging.info(f"🧹 Message MQTT conservé obsolète effacé : {msg.topic}")
        return True

    def _broadcast_to_ws(self, payload: dict):
        """Émet un message sur le WebSocket FastAPI depuis le thread Paho MQTT."""
        loop = self.main_loop
        if loop is None or not loop.is_running():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast(payload),
                loop
            )
            logging.debug(f"📡 Broadcast WS transmis à l'Event Loop: {payload.get('type')}")
        else:
            logging.warning("⚠️ Impossible d'émettre sur WS: Aucune event loop active trouvée")

    def _is_connected(self) -> bool:
        return self.client.is_connected()

    def connect(self, host: str = None, port: int = None):
        try:
            mqtt_conf = settings.mqtt
            broker_host = host or mqtt_conf.host
            broker_port = port or mqtt_conf.port

            try:
                self.main_loop = asyncio.get_running_loop()
            except RuntimeError:
                self.main_loop = asyncio.get_event_loop()

            self.client.on_connect = self.on_connect
            self.client.on_message = self.on_message
            self.client.on_disconnect = self.on_disconnect
            # Backoff avant chaque tentative de reconnexion (auto, gérée par
            # le thread du network loop une fois loop_start() lancé).
            self.client.reconnect_delay_set(min_delay=1, max_delay=60)

            if mqtt_conf.user and mqtt_conf.password:
                self.client.username_pw_set(mqtt_conf.user, mqtt_conf.password)

            # connect_async() ne bloque pas et ne lève pas d'exception si le
            # broker est injoignable : la connexion (et les reconnexions en
            # cas d'échec) est gérée par le thread réseau démarré par
            # loop_start(). Avec l'ancien connect() bloquant, un broker
            # injoignable au démarrage de l'API levait une exception AVANT
            # loop_start() : plus aucune tentative n'était jamais refaite,
            # y compris quand le broker revenait, jusqu'à un redémarrage
            # manuel du process.
            self.client.connect_async(broker_host, broker_port, mqtt_conf.timeout)
            self.client.loop_start()
            logging.info(f"✅ MQTT en cours de connexion au broker {broker_host}:{broker_port}...")
        except Exception as e:
            logging.error(f"❌ Erreur connexion MQTT: {e}")

    def on_disconnect(self, client, userdata, rc, properties=None):
        if rc != 0:
            logging.warning(f"⚠️ Déconnecté du broker MQTT (code {rc}), tentative de reconnexion automatique...")

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logging.info("📡 Broker MQTT connecté avec succès, abonnement aux topics...")
            self.client.subscribe(f"{self.topic_prefix}/controller/discovery/response")
            self.client.subscribe(f"{self.topic_prefix}/+/status")
            self.client.subscribe(f"{self.topic_prefix}/+/+/+/state")
            self.client.subscribe(f"{self.topic_prefix}/+/+/+/mode")
            self.client.subscribe(f"{self.topic_prefix}/+/switch/+/fault")
            self.client.subscribe(f"{self.topic_prefix}/+/notify")
            self.client.subscribe(f"{self.topic_prefix}/+/logs")
        else:
            logging.error(f"❌ Échec de connexion MQTT, code retour: {rc}")

    def on_message(self, client, userdata, msg):
        logging.debug(f"--- MESSAGE REÇU --- Topic: {msg.topic} | Payload: {msg.payload.decode()}")

        db = self.db_session_factory()
        try:
            topic_parts = msg.topic.split('/')

            # 0. Message conservé (retained) d'un équipement ou capteur qui n'existe plus
            # sous ce nom (renommé puis reflashé, supprimé) : effacé du broker
            if getattr(msg, "retain", False) and self._clear_stale_retained(db, topic_parts, msg):
                return

            # 1. Découverte ESPHome / Contrôleurs
            if msg.topic == f"{self.topic_prefix}/controller/discovery/response":
                payload = json.loads(msg.payload.decode())
                if self.discovery_future and not self.discovery_future.done():
                    name = payload.get("name")
                    ctrl_type = payload.get("type")
                    logging.info(f"🔎 Appareil trouvé : {name} ({ctrl_type})")

                    if self.main_loop and self.main_loop.is_running():
                        self.main_loop.call_soon_threadsafe(
                            self.discovery_future.set_result, {"name": name, "type": ctrl_type}
                        )

            # 2. Statut en ligne/hors ligne du contrôleur
            elif len(topic_parts) == 3 and topic_parts[2] == "status":
                controller_technical_name = topic_parts[1]
                # ESPHome publie « offline » (minuscules) à l'arrêt propre (flash, reboot)
                new_status = msg.payload.decode().strip().upper()
                if new_status in ("ONLINE", "OFFLINE"):
                    self._update_controller_status(db, controller_technical_name, new_status)
                else:
                    logging.warning(f"⚠️ Statut de contrôleur inattendu ignoré ({msg.topic}) : {new_status!r}")

            # 3. État d'un équipement (Relais ON/OFF)
            elif len(topic_parts) >= 5 and topic_parts[-3] == "switch" and topic_parts[-1] == "state":
                eq_technical_name = topic_parts[-2]
                real_state = msg.payload.decode()

                eq_id = self._update_equipment_status(db, eq_technical_name, real_state)

                self._broadcast_to_ws({
                    "type": "EQUIPMENT_STATE",
                    "equipment_id": eq_id,
                    "equipment_name": eq_technical_name,
                    "state": real_state
                })

            # 4. Mode d'un équipement (AUTO/MANUAL)
            elif len(topic_parts) >= 5 and topic_parts[-3] == "switch" and topic_parts[-1] == "mode":
                eq_technical_name = topic_parts[-2]
                new_mode = msg.payload.decode().upper()

                EquipmentService.update_mode(db, eq_technical_name, new_mode)

                equipment = db.query(Equipment).filter(firmware_name_column(Equipment) == eq_technical_name).first()
                eq_id = equipment.id if equipment else None

                self._broadcast_to_ws({
                    "type": "EQUIPMENT_MODE_UPDATE",
                    "equipment_id": eq_id,
                    "equipment_name": eq_technical_name,
                    "mode": new_mode
                })

            # 4b. Défaut d'un équipement (osmolateur : timeout, trop de
            # cycles ; interlock capteur ; ou "OK" = résolution)
            elif len(topic_parts) >= 5 and topic_parts[-3] == "switch" and topic_parts[-1] == "fault":
                controller_technical_name = topic_parts[1]
                eq_technical_name = topic_parts[-2]
                payload = msg.payload.decode().strip()
                self._handle_fault_message(db, controller_technical_name, eq_technical_name, payload)

            # 5. Relevés des capteurs (Sensors & Binary Sensors)
            # État réel des canaux d'une lampe (publié par l'ESP, chaque seconde en démo) :
            # relayé en direct sans écriture en base
            elif len(topic_parts) == 5 and topic_parts[2] == "light" and topic_parts[4] == "state":
                payload = json.loads(msg.payload.decode())
                self._broadcast_to_ws({
                    "type": "LIGHT_STATE",
                    "light_id": int(topic_parts[3]),
                    "channels": {k: v for k, v in payload.items() if k.isdigit()},
                    "demo": bool(payload.get("demo")),
                    "minute": payload.get("minute"),
                })

            elif len(topic_parts) == 5 and topic_parts[4] == "state" and topic_parts[2] in ["sensor", "binary_sensor"]:
                controller_id = topic_parts[1]
                component_type = topic_parts[2]
                sensor_technical_name = topic_parts[3]
                raw_value = msg.payload.decode().strip()

                parsed_value = None
                no_reading = False
                if component_type == "binary_sensor" or raw_value.upper() in ["ON", "OFF", "TRUE", "FALSE"]:
                    parsed_value = 1.0 if raw_value.upper() in ["ON", "TRUE", "1"] else 0.0
                else:
                    try:
                        parsed_value = float(raw_value)
                    except ValueError:
                        logging.error(f"Valeur numérique invalide pour {sensor_technical_name}: '{raw_value}'")
                    # ESPHome publie "nan" quand une sonde (ex: DS18B20) ne répond pas
                    if parsed_value is not None and not math.isfinite(parsed_value):
                        logging.warning(f"Pas de mesure pour {sensor_technical_name}: '{raw_value}'")
                        parsed_value = None
                        no_reading = True

                if no_reading:
                    # Sonde débranchée ou qui ne répond plus : plus de dernière valeur affichée
                    sensor_id = self._clear_sensor_value(db, controller_id, sensor_technical_name)
                    if sensor_id:
                        self._broadcast_to_ws({
                            "type": "SENSOR_READING",
                            "sensor_id": sensor_id,
                            "controller_id": controller_id,
                            "sensor_name": sensor_technical_name,
                            "value": None,
                        })

                if parsed_value is not None:
                    sensor_id, final_value = self._save_sensor_reading(db, controller_id, sensor_technical_name, parsed_value)

                    if sensor_id and final_value is not None:
                        self._broadcast_to_ws({
                            "type": "SENSOR_READING",
                            "sensor_id": sensor_id,
                            "controller_id": controller_id,
                            "sensor_name": sensor_technical_name,
                            "value": final_value
                        })
            # 6. Journaux des contrôleurs (<prefix>/<contrôleur>/logs) : JSON
            # {level, component, message} ou texte brut
            elif len(topic_parts) == 3 and topic_parts[2] == "logs":
                controller_technical_name = topic_parts[1]
                payload_raw = msg.payload.decode()

                log_level = "I"
                log_component = "system"
                log_message = payload_raw
                try:
                    data_json = json.loads(payload_raw)
                    if isinstance(data_json, dict):
                        log_level = data_json.get("level", "I")
                        log_component = data_json.get("component", "system")
                        log_message = data_json.get("message", payload_raw)
                except json.JSONDecodeError:
                    pass

                self._save_controller_log(db, controller_technical_name, log_level, log_component, log_message)

            # 7. Notification simple, sans équipement (ex: réserve pleine)
            elif len(topic_parts) == 3 and topic_parts[2] == "notify":
                controller_technical_name = topic_parts[1]
                message = msg.payload.decode().strip()
                self._handle_notify_message(db, controller_technical_name, message)

        except Exception as e:
            db.rollback()
            logging.error(f"Erreur traitement message MQTT ({msg.topic}): {e}")
        finally:
            db.close()


    def _update_controller_status(self, db, controller_technical_name: str, status: str):
        controller = db.query(Controller).filter_by(technical_name=controller_technical_name).first()
        if controller:
            controller.status = status
            db.commit()

            self._broadcast_to_ws({
                "type": "CONTROLLER_STATUS",
                "controller_name": controller.technical_name,
                "status": status
            })
        else:
            logging.warning(f"⚠️ Contrôleur introuvable pour status update: {controller_technical_name}")

    def _handle_fault_message(self, db, controller_technical_name: str, eq_technical_name: str, payload: str):
        controller = db.query(Controller).filter_by(technical_name=controller_technical_name).first()
        if not controller:
            logging.warning(f"⚠️ Contrôleur introuvable pour fault: {controller_technical_name}")
            return

        equipment = db.query(Equipment).filter(firmware_name_column(Equipment) == eq_technical_name).first()
        eq_id = equipment.id if equipment else None

        open_fault = (
            db.query(EquipmentFault)
            .filter(
                EquipmentFault.controller_id == controller.id,
                EquipmentFault.equipment_id == eq_id,
                EquipmentFault.resolved_at.is_(None),
            )
            .order_by(EquipmentFault.created_at.desc())
            .first()
        )

        if payload == "OK":
            if open_fault:
                open_fault.resolved_at = datetime.now()
                db.commit()
                self._broadcast_to_ws({
                    "type": "EQUIPMENT_FAULT",
                    "id": open_fault.id,
                    "equipment_id": eq_id,
                    "equipment_name": eq_technical_name,
                    "code": "OK",
                    "resolved": True,
                })
            return

        code = payload
        if open_fault and open_fault.code == code:
            # Défaut déjà ouvert et identique : pas de doublon, pas de
            # nouvelle notification (évite le spam si un capteur d'interlock
            # oscille pendant que la condition reste dangereuse).
            return

        latched = code in LATCHED_FAULT_CODES
        message = f"{eq_technical_name}: {code}"
        fault = EquipmentFault(
            controller_id=controller.id,
            equipment_id=eq_id,
            code=code,
            message=message,
            latched=latched,
        )
        db.add(fault)
        db.commit()
        db.refresh(fault)

        self._broadcast_to_ws({
            "type": "EQUIPMENT_FAULT",
            "id": fault.id,
            "equipment_id": eq_id,
            "equipment_name": eq_technical_name,
            "code": code,
            "message": message,
            "latched": latched,
            "resolved": False,
        })

        subject = f"[AquasManager] Défaut {eq_technical_name}: {code}"
        notify.dispatch_alert(subject, message, priority="high")

    def _handle_notify_message(self, db, controller_technical_name: str, message: str):
        controller = db.query(Controller).filter_by(technical_name=controller_technical_name).first()
        if not controller:
            logging.warning(f"⚠️ Contrôleur introuvable pour notify: {controller_technical_name}")
            return

        now = datetime.now()
        fault = EquipmentFault(
            controller_id=controller.id,
            equipment_id=None,
            code="NOTIFY",
            message=message,
            latched=False,
            resolved_at=now,  # notification instantanée, pas un état ouvert
        )
        db.add(fault)
        db.commit()
        db.refresh(fault)

        self._broadcast_to_ws({
            "type": "EQUIPMENT_FAULT",
            "id": fault.id,
            "equipment_id": None,
            "equipment_name": None,
            "code": "NOTIFY",
            "message": message,
            "latched": False,
            "resolved": True,
        })

        notify.dispatch_alert(f"[AquasManager] {controller.name}", message)

    def _update_equipment_status(self, db, equipment_identifier: str, status: str) -> Optional[int]:
        equipment = db.query(Equipment).filter(firmware_name_column(Equipment) == equipment_identifier).first()
        if not equipment:
            logging.warning(f"⚠️ Équipement introuvable en BDD: {equipment_identifier}")
            return None

        new_status = status.upper()
        old_status = equipment.status.value if equipment.status else None
        equipment.status = new_status

        # Ne journalise une transition que si l'état a réellement changé
        # (un message retenu rejoué avec le même état ne doit pas créer une
        # nouvelle activation ni fausser les statistiques).
        if new_status != old_status and new_status in ("ON", "OFF"):
            self._record_activation_transition(db, equipment, new_status)

        db.commit()
        return equipment.id

    def _record_activation_transition(self, db, equipment, new_status: str):
        if new_status == "ON":
            db.add(EquipmentActivation(equipment_id=equipment.id, started_at=datetime.now()))
            return

        # new_status == "OFF" : referme la dernière activation encore ouverte.
        open_activation = (
            db.query(EquipmentActivation)
            .filter(EquipmentActivation.equipment_id == equipment.id, EquipmentActivation.ended_at.is_(None))
            .order_by(EquipmentActivation.started_at.desc())
            .first()
        )
        if open_activation:
            ended_at = datetime.now()
            open_activation.ended_at = ended_at
            open_activation.duration_seconds = int((ended_at - open_activation.started_at).total_seconds())
            # Compteur d'heures cumulé (usure, entretien), indépendant de la purge des activations
            record_runtime(db, equipment.id, open_activation.duration_seconds)

    def _clear_sensor_value(self, db, controller_identifier, sensor_technical_name: str) -> Optional[int]:
        """Mesure absente (« nan ») : dernière valeur effacée, sans relevé dans l'historique."""
        controller = db.query(Controller).filter(
            (Controller.technical_name == str(controller_identifier)) | (Controller.name == str(controller_identifier))
        ).first()
        if not controller:
            return None
        sensor = db.query(Sensor).filter(
            Sensor.controller_id == controller.id,
            firmware_name_column(Sensor) == sensor_technical_name,
        ).first()
        if not sensor:
            return None
        if sensor.last_value is not None:
            sensor.last_value = None
            db.commit()
        return sensor.id

    @staticmethod
    def _find_controller(db, controller_identifier) -> Optional[Controller]:
        """Contrôleur désigné dans un topic : id numérique, nom technique ou nom affiché."""
        controller = None
        if str(controller_identifier).isdigit():
            controller = db.query(Controller).filter(Controller.id == int(controller_identifier)).first()
        if not controller:
            controller = db.query(Controller).filter(
                (Controller.technical_name == str(controller_identifier)) |
                (Controller.name == str(controller_identifier))
            ).first()
        return controller

    def _save_sensor_reading(self, db, controller_identifier, sensor_technical_name: str, value: float) -> Tuple[Optional[int], Optional[float]]:
        """Enregistre une mesure (inversée pour les capteurs binaires marqués is_inverted) ; retourne (id du capteur, valeur retenue)."""
        controller = self._find_controller(db, controller_identifier)
        if not controller:
            logging.warning(f"⚠️ Contrôleur non trouvé en BDD : {controller_identifier}")
            return None, None

        sensor = db.query(Sensor).filter(
            Sensor.controller_id == controller.id,
            firmware_name_column(Sensor) == sensor_technical_name
        ).first()

        if sensor:
            final_value = float(value)
            if getattr(sensor, 'is_inverted', False) and final_value in [0.0, 1.0]:
                final_value = 0.0 if final_value == 1.0 else 1.0

            reading = SensorReading(sensor_id=sensor.id, value=final_value)
            db.add(reading)
            sensor.last_value = str(final_value)
            sensor.last_reading_at = datetime.now()
            db.commit()

            return sensor.id, final_value
        else:
            logging.warning(f"⚠️ Capteur non trouvé : ctrl={controller.id}, name={sensor_technical_name}")
            return None, None

    def _save_controller_log(self, db, controller_identifier: str, level: str, component: str, message: str):
        """Enregistre une ligne de journal publiée par un contrôleur."""
        controller = self._find_controller(db, controller_identifier)
        if not controller:
            logging.warning(f"⚠️ Contrôleur non trouvé pour le log : {controller_identifier}")
            return

        db.add(LogModel(controller_id=controller.id, level=level, component=component, message=message))
        db.commit()
        logging.debug(f"📝 Log enregistré pour [{controller.technical_name}] ({level}/{component}): {message}")

    def publish(self, sub_topic: str, data: any, retain=False, qos=0):
        topic = f"{self.topic_prefix}/{sub_topic}"
        payload = data if isinstance(data, (str, bytes)) else json.dumps(data)
        if settings.demo:
            # Démo : pas de broker, le contrôleur simulé répond directement
            from services.demo import echo_command

            echo_command(self, topic, payload)
            return
        self.client.publish(topic, payload, retain=retain, qos=qos)
        logging.debug(f"MQTT Out -> {topic}")


mqtt_driver = MQTTDriver()