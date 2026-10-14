"""
Contrôleurs ESP32 : fiche, découverte réseau, broches, modules, scans
1-Wire / I2C, génération et flash du firmware ESPHome.
"""

import difflib
import logging
import re
from services.technical_names import firmware_flashed
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from services.tools import generate_technical_name
from services.discovery import scan_network_for_esphome
from services.one_wire_scan import scan_i2c_devices, scan_one_wire_devices
from services.controller import (
    add_io_module_to_controller,
    flash_in_progress,
    flash_states,
    get_io_modules_for_controller,
    update_io_module,
    delete_io_module,
    queue_flash,
    run_esphome_ota,
)
from middleware.auth import min_role_required
from middleware.database import get_db
from models.controller import Controller
from models.controller_pin import ControllerPin
from models.sensor import Sensor
from models.rule import Rule
from models.rule_condition import RuleCondition
from schemas.controller import (
    ControllerCreate,
    ControllerListResponse,
    ControllerRead,
    ControllerUpdate,
)
from schemas.io_module import ModuleCreate, ModuleUpdate
from schemas.sensor import normalize_one_wire_address
from services.esphome_generator import generate_esphome_yaml
from services.pins import i2c_role
from models.sensor import is_temperature_sensor
from drivers.mqtt import mqtt_driver
from services.controller import create_new_controller
from utils.network import get_next_available_ip
from services.websocket import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/controllers",
    tags=["controllers"],
    dependencies=[Depends(min_role_required("consult"))]
)


# =====================================================================
# 1. ROUTES STATIQUES & ACTIONS SPÉCIFIQUES (Placées EN PREMIER)
# =====================================================================

@router.get("/scan", status_code=status.HTTP_200_OK)
def scan_esphome_controller(
    timeout: int = Query(3, ge=1, le=10, description="Temps de recherche en secondes")
):
    """
    Scanne le réseau local (mDNS / Zeroconf) pour détecter les cartes
    exécutant ESPHome et retourne leur nom, IP et type.
    """
    devices = scan_network_for_esphome(timeout=timeout)
    return devices


@router.get("/flash-status")
def get_flash_status():
    """Flashs en cours ou récents (progression affichée après un rechargement de page)."""
    return flash_states()


@router.get("/", response_model=ControllerListResponse)
def list_controllers(db: Session = Depends(get_db)):
    items = db.query(Controller).all()
    return {"total": len(items), "controllers": items}


@router.post(
    "/",
    response_model=ControllerRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(min_role_required("manager"))],
)
def create_controller(controller: ControllerCreate, db: Session = Depends(get_db)):
    return create_new_controller(db, controller)


# PLACEMENT OBLIGATOIRE ICI (Avant /{controller_id})
@router.get("/next-available-ip")
def get_available_ip(
    subnet: str = Query("192.168.1", description="Base du sous-réseau ex: 192.168.1"),
    start_host: int = Query(50, description="Hôte de début (ex: 50)"),
    end_host: int = Query(99, description="Hôte de fin (ex: 99)"),
    db: Session = Depends(get_db)
):
    start_ip = f"{subnet}.{start_host}"
    end_ip = f"{subnet}.{end_host}"

    try:
        ip = get_next_available_ip(db, start_ip=start_ip, end_ip=end_ip)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not ip:
        raise HTTPException(status_code=404, detail="Aucune IP disponible dans cette plage.")

    return {"ip": ip}


# =====================================================================
# 2. ROUTES DYNAMIQUES /{controller_id} (Placées EN SECOND)
# =====================================================================

@router.post("/{controller_id}/flash", dependencies=[Depends(min_role_required("manager"))])
async def flash_controller_ota(
    controller_id: int,
    background_tasks: BackgroundTasks,
    target_ip: Optional[str] = Query(
        None,
        description="IP temporaire (issue du scan) si c'est un premier flash d'adoption."
    ),
    db: Session = Depends(get_db)
):
    """
    Génère la config YAML et lance le flash OTA vers l'ESP.
    """
    controller = db.query(Controller).filter(Controller.id == controller_id).first()
    if not controller:
        raise HTTPException(status_code=404, detail="Contrôleur non trouvé.")
    if flash_in_progress(controller_id):
        raise HTTPException(status_code=409, detail="Un flash de ce contrôleur est déjà en cours.")

    # Détermination de l'IP cible pour le push OTA
    destination_ip = target_ip or controller.ip
    if not destination_ip:
        raise HTTPException(
            status_code=400,
            detail="Aucune IP cible spécifiée et aucune IP fixe attribuée au contrôleur."
        )

    # 1. Génération du YAML avec les réglages actuels
    yaml_content = generate_esphome_yaml(controller)
    controller.yaml_config = yaml_content
    controller.status = "FLASHING"
    db.commit()

    await ws_manager.broadcast({
        "type": "CONTROLLER_STATUS",
        "controller_name": controller.technical_name,
        "controller_id": controller_id,
        "status": "FLASHING"
    })

    # 2. Lancement de la tâche OTA en arrière-plan pour ne pas bloquer l'API
    #    (un seul flash à la fois : les suivants attendent leur tour)
    await queue_flash(controller.id, controller.technical_name)
    background_tasks.add_task(
        run_esphome_ota,
        controller_id=controller.id,
        yaml_content=yaml_content,
        target_ip=destination_ip,
    )

    return {
        "message": f"Flash OTA démarré vers {destination_ip}.",
        "controller_id": controller.id,
        "target_ip": destination_ip,
        "status": "FLASHING"
    }


@router.get("/{controller_id}", response_model=ControllerRead)
def get_controller(controller_id: int, db: Session = Depends(get_db)):
    controller = db.query(Controller).filter(Controller.id == controller_id).first()
    if not controller:
        raise HTTPException(status_code=404, detail="Contrôleur non trouvé")
    return controller


@router.patch(
    "/{controller_id}",
    response_model=ControllerRead,
    dependencies=[Depends(min_role_required("manager"))],
)
def update_controller(
    controller_id: int,
    update_data: ControllerUpdate,
    db: Session = Depends(get_db)  # <--- Indispensable ici !
) -> Controller:
    controller = db.query(Controller).filter(Controller.id == controller_id).first()
    if not controller:
        raise HTTPException(status_code=404, detail="Contrôleur non trouvé")

    update_dict = update_data.model_dump(exclude_unset=True)

    # Si le nom est mis à jour, on met à jour automatiquement le technical_name
    if "name" in update_dict and update_dict["name"] != controller.name:
        controller.name = update_dict["name"]
        new_technical_name = generate_technical_name(update_dict["name"])
        if new_technical_name != controller.technical_name:
            controller.technical_name = new_technical_name
            controller.is_dirty = True  # les topics MQTT changent avec le nom technique
        update_dict.pop("name")
        update_dict.pop("technical_name", None)

    if "rtc_model" in update_dict and update_dict["rtc_model"] is None and controller.rtc_model:
        _ensure_rtc_not_needed(db, controller)

    updated = False
    for field, value in update_dict.items():
        if getattr(controller, field) != value:
            setattr(controller, field, value)
            updated = True
            if field in ("rtc_model", "i2c_frequency_khz"):
                controller.is_dirty = True  # horloge et bus I2C font partie du firmware

    if "name" in update_data.model_dump(exclude_unset=True):
        updated = True

    if updated:
        db.commit()
        db.refresh(controller)

    return controller


def _ensure_rtc_not_needed(db: Session, controller: Controller) -> None:
    """Refuse de retirer l'horloge tant qu'une lampe ou une règle horaire en dépend."""
    if any(light.light_channels for light in controller.lights):
        raise HTTPException(status_code=409, detail="Des lampes de ce contrôleur ont besoin de l'horloge : supprime-les d'abord.")
    time_rule = (
        db.query(RuleCondition).join(Rule, Rule.id == RuleCondition.rule_id)
        .filter(RuleCondition.condition_type == "TIME_RANGE")
        .all()
    )
    for condition in time_rule:
        rule = condition.rule
        targets = [rule.equipment] if rule.equipment else list(rule.group.equipments) if rule.group else []
        sensors = [c.sensor for c in rule.conditions if c.sensor is not None]
        if any(item.controller_id == controller.id for item in targets + sensors):
            raise HTTPException(
                status_code=409,
                detail=f"La règle « {rule.name} » utilise une plage horaire sur ce contrôleur : supprime-la d'abord.",
            )


@router.delete(
    "/{controller_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(min_role_required("manager"))],
)
def delete_controller(controller_id: int, db: Session = Depends(get_db)):
    controller = db.query(Controller).filter(Controller.id == controller_id).first()
    if not controller:
        raise HTTPException(status_code=404, detail="Contrôleur non trouvé")

    db.delete(controller)
    db.commit()


@router.get("/{controller_id}/pins")
def get_available_pins(
    controller_id: int,
    include_pin_id: Optional[int] = Query(None, description="Broche actuelle de l'élément en cours de modification"),
    include_used: bool = Query(False, description="Renvoyer aussi les broches occupées (free: false, used_by)"),
    db: Session = Depends(get_db),
):
    """Broches libres, ou toutes avec include_used. Pour chacune :
    - free : utilisable par un nouvel élément quelconque ;
    - one_wire : bus 1-Wire partagé (encore possible pour une sonde de température) ;
    - used_by : ce qui l'occupe (« Écumeur · Récif », « Bus 1-Wire : … », « Bus I2C (SDA) »)."""

    def owner_label(owner) -> str:
        return f"{owner.name} · {owner.aquarium.name}" if getattr(owner, "aquarium", None) else owner.name

    def describe(pin: ControllerPin) -> dict:
        role = i2c_role(pin)
        if role:
            return {"free": False, "one_wire": False, "used_by": f"Bus I2C ({role})"}
        if pin.id == include_pin_id:
            return {"free": True, "one_wire": False, "used_by": None}
        probes = [s for s in (pin.sensors or []) if is_temperature_sensor(s)]
        if probes:
            names = ", ".join(owner_label(s) for s in probes)
            return {"free": False, "one_wire": True, "used_by": f"Bus 1-Wire : {names}"}
        owners = ([pin.equipment] if pin.equipment is not None else []) + list(pin.sensors or [])
        if owners:
            return {"free": False, "one_wire": False, "used_by": owner_label(owners[0])}
        if pin.lights_channel is not None:
            return {"free": False, "one_wire": False, "used_by": pin.lights_channel.name}
        # Marquée occupée mais plus rien dessus (ancienne donnée) : libre en réalité
        return {"free": True, "one_wire": False, "used_by": None}

    pins = db.query(ControllerPin).filter(ControllerPin.controller_id == controller_id).all()
    states = {p.id: describe(p) for p in pins}
    # Sans include_used : broches libres et bus 1-Wire partageable
    free_pins = pins if include_used else [p for p in pins if states[p.id]["free"] or states[p.id]["one_wire"]]

    return {
        "controller_pins": [
            {
                "id": p.id,
                "pin_number": p.pin_number,
                "mode": p.mode,
                "controller_id": p.controller_id,
                "module_id": p.module_id,
                "module_number": p.io_module.number if p.io_module else None,
                "module_type": str(getattr(p.io_module.type, "value", p.io_module.type)) if p.io_module else None,
                **states[p.id],
            } for p in free_pins
        ],
        "total": len(free_pins)
    }


@router.get("/{controller_id}/one-wire/scan", dependencies=[Depends(min_role_required("user"))])
async def scan_one_wire(controller_id: int, db: Session = Depends(get_db)):
    controller = db.query(Controller).filter(Controller.id == controller_id).first()
    if not controller:
        raise HTTPException(status_code=404, detail="Contrôleur non trouvé")
    if not controller.ip:
        raise HTTPException(status_code=400, detail="Ce contrôleur n'a pas d'adresse IP.")

    try:
        result = await scan_one_wire_devices(controller.ip)
    except Exception as e:
        logger.warning("Scan 1-Wire impossible sur %s (%s): %s", controller.technical_name, controller.ip, e)
        raise HTTPException(
            status_code=502,
            detail=f"Impossible de joindre le contrôleur {controller.name} ({controller.ip}) via l'API ESPHome.",
        )

    probes = [s for s in db.query(Sensor).filter(Sensor.controller_id == controller_id) if s.unit == "°C"]

    def key(address):
        try:
            return normalize_one_wire_address(address)
        except ValueError:
            return address

    assigned = {key(s.address): s for s in probes if s.address}
    # Sonde enregistrée sans adresse, seule sur sa broche : le firmware lit la seule
    # sonde du bus, c'est donc elle
    per_pin: dict = {}
    for device in result["devices"]:
        per_pin.setdefault(device["pin_number"], []).append(device)
    for sensor in probes:
        pin_number = int(sensor.pin.pin_number) if sensor.pin and str(sensor.pin.pin_number).isdigit() else None
        same_pin = [s for s in probes if s.pin_id == sensor.pin_id]
        found = per_pin.get(pin_number, [])
        if not sensor.address and len(same_pin) == 1 and len(found) == 1:
            assigned.setdefault(found[0]["address"], sensor)

    for device in result["devices"]:
        sensor = assigned.get(device["address"])
        device["sensor_id"] = sensor.id if sensor else None
        device["sensor_name"] = sensor.name if sensor else None
        # Aquarium et dernière mesure : reconnaître une sonde sans ouvrir sa fiche
        device["aquarium_name"] = sensor.aquarium.name if sensor and sensor.aquarium else None
        device["last_value"] = sensor.last_value if sensor else None

    # Diagnostic quand rien n'est trouvé : pas de configuration reçue, pas de bus
    # dans le firmware, ou bus présent sans sonde qui réponde (câblage)
    return result


@router.post("/{ctrl_id}/modules", dependencies=[Depends(min_role_required("manager"))])
async def add_io_module(ctrl_id: int, module_data: ModuleCreate, db: Session = Depends(get_db)):
    module_id = add_io_module_to_controller(db, ctrl_id, module_data)
    return {"status": "success", "module_id": module_id}


@router.get("/{ctrl_id}/modules")
async def get_io_modules(ctrl_id: int, db: Session = Depends(get_db)):
    modules = get_io_modules_for_controller(db, ctrl_id)
    return modules


@router.patch("/{ctrl_id}/modules/{module_ref}", dependencies=[Depends(min_role_required("manager"))])
def patch_io_module(ctrl_id: int, module_ref: str, data: ModuleUpdate, db: Session = Depends(get_db)):
    """Numéro, adresse ou type d'un module (identifiant ou adresse I2C) ; ses broches et
    ce qui y est branché sont gardés."""
    return update_io_module(db, ctrl_id, module_ref, data)


@router.delete("/{ctrl_id}/modules/{module_ref}", status_code=204, dependencies=[Depends(min_role_required("manager"))])
def remove_io_module(ctrl_id: int, module_ref: str, db: Session = Depends(get_db)):
    delete_io_module(db, ctrl_id, module_ref)


# Adresses I2C fixes des horloges RTC (définies par la puce)
RTC_ADDRESSES = {"DS3231": "0x68", "DS1307": "0x68", "PCF8563": "0x51", "PCF85063": "0x51"}


@router.get("/{controller_id}/i2c/scan", dependencies=[Depends(min_role_required("user"))])
async def scan_i2c(controller_id: int, db: Session = Depends(get_db)):
    """Appareils détectés sur le bus I2C (scan fait par le firmware au démarrage),
    identifiés : module déclaré, horloge, mémoire de l'horloge, module non déclaré."""
    controller = db.query(Controller).filter(Controller.id == controller_id).first()
    if not controller:
        raise HTTPException(status_code=404, detail="Contrôleur non trouvé")
    if not controller.ip:
        raise HTTPException(status_code=400, detail="Ce contrôleur n'a pas d'adresse IP.")
    try:
        result = await scan_i2c_devices(controller.ip)
    except Exception as e:
        logger.warning("Scan I2C impossible sur %s (%s): %s", controller.technical_name, controller.ip, e)
        raise HTTPException(
            status_code=502,
            detail=f"Impossible de joindre le contrôleur {controller.name} ({controller.ip}) via l'API ESPHome.",
        )

    modules = {m.address.lower(): m for m in get_io_modules_for_controller(db, controller_id)}
    rtc_address = RTC_ADDRESSES.get(controller.rtc_model or "")
    devices = []
    for address in result["addresses"]:
        value = int(address, 16)
        module = modules.get(address)
        if module:
            kind = "module"
        elif address == rtc_address:
            kind = "rtc"
        elif value in (0x68, 0x51):
            kind = "rtc_undeclared"
        elif 0x50 <= value <= 0x57:
            kind = "eeprom"
        elif 0x20 <= value <= 0x27 or 0x38 <= value <= 0x3F:
            kind = "io_undeclared"
        elif value == 0x70 and any(str(getattr(m.type, "value", m.type)) == "PCA9685" for m in modules.values()):
            kind = "pca_allcall"  # adresse commune à tous les PCA9685, rien à déclarer
        elif 0x40 <= value <= 0x4F:
            kind = "pwm_undeclared"
        else:
            kind = "unknown"
        devices.append({
            "address": address,
            "kind": kind,
            "module_number": module.number if module else None,
            "module_type": str(module.type) if module else None,
        })
    found = set(result["addresses"])
    missing = [
        {"address": a, "module_number": m.number, "module_type": str(m.type)}
        for a, m in sorted(modules.items(), key=lambda kv: kv[1].number) if a not in found
    ]
    if rtc_address and rtc_address not in found:
        missing.append({"address": rtc_address, "rtc": controller.rtc_model})
    return {"enabled": result["enabled"], "devices": devices, "missing": missing if result["enabled"] else []}


# Valeurs secrètes (Wi-Fi, MQTT, clés) masquées avant tout affichage du YAML
_SECRET_LINE_RE = re.compile(r"^(\s*(?:-\s*)?[\w-]*(?:password|secret|token|key)\s*:\s*)(\S.*)$", re.IGNORECASE)


def mask_yaml_secrets(content: Optional[str]) -> Optional[str]:
    if content is None:
        return None
    lines = str(content).replace("\u00A0", " ").replace("\r\n", "\n").split("\n")
    return "\n".join(_SECRET_LINE_RE.sub(r'\1"••••••"', line) for line in lines)


def _config_diff(controller: Controller, deployed: str, desired: str) -> str:
    return "".join(
        difflib.unified_diff(
            deployed.splitlines(keepends=True),
            desired.splitlines(keepends=True),
            fromfile=f"deploye_{controller.technical_name}.yaml",
            tofile=f"a_deployer_{controller.technical_name}.yaml",
            n=3,
        )
    )


@router.get("/{controller_id}/config", dependencies=[Depends(min_role_required("manager"))])
def get_controller_config(controller_id: int, db: Session = Depends(get_db)):
    """
    Configuration ESPHome déployée (dernier flash réussi), configuration à
    déployer (générée à partir de l'état actuel) et leurs différences.
    Les mots de passe et clés sont masqués.
    """
    controller = db.query(Controller).filter(Controller.id == controller_id).first()
    if not controller:
        raise HTTPException(status_code=404, detail="Contrôleur non trouvé")

    deployed = mask_yaml_secrets(controller.last_config)
    desired = mask_yaml_secrets(generate_esphome_yaml(controller))
    return {
        "deployed": deployed,
        "desired": desired,
        "diff": _config_diff(controller, deployed or "", desired) if deployed else None,
        "identical": deployed is not None and deployed.strip() == desired.strip(),
        "last_sync": controller.last_sync,
        "is_dirty": controller.is_dirty,
    }


@router.get("/{controller_id}/yaml", dependencies=[Depends(min_role_required("manager"))])
def get_controller_yaml(controller_id: int, db: Session = Depends(get_db)):
    controller = db.query(Controller).filter(Controller.id == controller_id).first()
    if not controller:
        raise HTTPException(status_code=404, detail="Contrôleur non trouvé")
    return {"yaml": mask_yaml_secrets(generate_esphome_yaml(controller))}


@router.get("/{controller_id}/diff", response_model=str, dependencies=[Depends(min_role_required("manager"))])
def get_controller_diff(controller_id: int, db: Session = Depends(get_db)):
    controller = db.query(Controller).filter(Controller.id == controller_id).first()
    if not controller:
        raise HTTPException(status_code=404, detail="Contrôleur introuvable")
    deployed = mask_yaml_secrets(controller.last_config) or ""
    diff_result = _config_diff(controller, deployed, mask_yaml_secrets(generate_esphome_yaml(controller)))
    return diff_result if diff_result else "Aucune modification en attente."


@router.post("/{controller_id}/restart", dependencies=[Depends(min_role_required("manager"))])
def restart_controller(controller_id: int, db: Session = Depends(get_db)):
    """Redémarre le contrôleur (bouton « restart » du firmware, via MQTT) : il refait
    alors le scan des bus I2C et 1-Wire."""
    controller = db.query(Controller).filter(Controller.id == controller_id).first()
    if not controller:
        raise HTTPException(status_code=404, detail="Contrôleur non trouvé")
    if "platform: restart" not in (controller.last_config or ""):
        raise HTTPException(
            status_code=409,
            detail="Le firmware de ce contrôleur ne sait pas encore redémarrer à distance : flashe-le une fois.",
        )
    # Le driver ajoute la racine des topics (restart_topic côté firmware)
    mqtt_driver.publish(f"{controller.technical_name}/button/restart/command", "PRESS", qos=1)
    return {"status": "sent"}


@router.post("/{controller_id}/sync_success", dependencies=[Depends(min_role_required("manager"))])
def mark_sync_success(controller_id: int, db: Session = Depends(get_db)):
    controller = db.query(Controller).filter(Controller.id == controller_id).first()
    if not controller:
        raise HTTPException(status_code=404, detail="Contrôleur non trouvé")

    controller.is_dirty = False
    controller.last_sync = datetime.now()
    # Flashé à la main avec la configuration actuelle : c'est elle qui est déployée
    controller.last_config = generate_esphome_yaml(controller)
    firmware_flashed(db, controller.id)
    db.commit()

    return {"status": "success", "last_sync": controller.last_sync}