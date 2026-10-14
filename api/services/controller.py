"""
Contrôleurs : création (broches de l'ESP32), modules d'extension I2C
(PCF8574/PCF8575/PCA9685) et flash du firmware (file d'attente, OTA ESPHome).
"""

# services/controller_service.py
import asyncio
from typing import Optional
import os
import re
import tempfile
import time
import logging
from services.technical_names import firmware_flashed
from collections import deque
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from middleware.database import SessionLocal
from models.controller import Controller
from models.controller_pin import ControllerPin
from models.io_module import IoModule
from models.logs import LogModel
from schemas.controller import ControllerCreate
from schemas.io_module import ModuleCreate
from utils.network import get_next_available_ip
from services.tools import notify_controller_update, generate_technical_name
from services.websocket import ws_manager

logger = logging.getLogger(__name__)


def create_new_controller(db: Session, controller_data: ControllerCreate) -> Controller:
    # 1. Vérification de l'unicité du nom
    if db.query(Controller).filter(Controller.name == controller_data.name).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un contrôleur avec ce nom existe déjà."
        )

    ip_to_assign = controller_data.ip

    # 2. Si une IP est fournie (ex: via scan network), on vérifie qu'elle n'est pas déjà prise
    if ip_to_assign:
        existing_ip = db.query(Controller).filter(Controller.ip == ip_to_assign).first()
        if existing_ip:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"L'adresse IP {ip_to_assign} est déjà attribuée au contrôleur '{existing_ip.name}'."
            )
    else:
        # 3. Fallback : Auto-attribution de la prochaine IP libre via la config
        ip_to_assign = get_next_available_ip(db)
        if not ip_to_assign:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Aucune adresse IP disponible dans la plage réservée."
            )

    technical_name = generate_technical_name(controller_data.name)

    # 4. Enregistrement en base de données
    data = controller_data.model_dump()
    data["ip"] = ip_to_assign
    data["technical_name"] = technical_name

    db_controller = Controller(**data)
    db.add(db_controller)
    db.commit()
    db.refresh(db_controller)

    return db_controller


PIN_COUNT = {"PCF8574": 8, "PCF8575": 16, "PCA9685": 16}


def _module_pins_used(db: Session, module: IoModule, from_pin: int = 0) -> list[str]:
    """Noms des équipements, capteurs ou canaux de lampe branchés sur le module."""
    from services.pins import pin_is_used

    used = []
    for pin in module.pins:
        if int(pin.pin_number) < from_pin:
            continue
        if pin_is_used(db, pin.id) or pin.lights_channel is not None:
            used.append(pin.label or f"broche {pin.pin_number}")
    return used


def _ensure_free(db: Session, ctrl_id: int, address: str, number: int, module_id: Optional[int] = None) -> None:
    for other in db.query(IoModule).filter(IoModule.controller_id == ctrl_id, IoModule.id != (module_id or 0)):
        if other.address.lower() == address:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Un module utilise déjà l'adresse {address} sur ce contrôleur.")
        if other.number == number:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Le numéro {number} est déjà pris par le module {other.address}.")


def _create_pins(db: Session, module: IoModule, start: int, count: int) -> None:
    db.add_all(
        ControllerPin(controller_id=module.controller_id, module_id=module.id, pin_number=str(i),
                      bus="I2C", mode="FREE", label="FREE")
        for i in range(start, count)
    )


def _mark_dirty(db: Session, ctrl_id: int) -> None:
    db.query(Controller).filter(Controller.id == ctrl_id).update({Controller.is_dirty: True})


def add_io_module_to_controller(db: Session, ctrl_id: int, module_data: ModuleCreate) -> int:
    if not db.get(Controller, ctrl_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contrôleur non trouvé")
    taken = {n for (n,) in db.query(IoModule.number).filter(IoModule.controller_id == ctrl_id)}
    number = module_data.number or next(n for n in range(1, 100) if n not in taken)
    _ensure_free(db, ctrl_id, module_data.address, number)
    module_type = str(module_data.type)
    new_module = IoModule(controller_id=ctrl_id, address=module_data.address, type=module_type, number=number)
    db.add(new_module)
    db.flush()
    _create_pins(db, new_module, 0, PIN_COUNT[module_type])
    _mark_dirty(db, ctrl_id)
    db.commit()

    notify_controller_update(ctrl_id, db)
    return new_module.id


def _get_module(db: Session, ctrl_id: int, module_ref: str) -> IoModule:
    """Module par identifiant ou par adresse I2C (0x20)."""
    query = db.query(IoModule).filter(IoModule.controller_id == ctrl_id)
    module = (
        query.filter(IoModule.id == int(module_ref)).first()
        if module_ref.isdigit()
        else next((m for m in query if m.address.lower() == module_ref.strip().lower()), None)
    )
    if not module:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Module introuvable sur ce contrôleur.")
    return module


def update_io_module(db: Session, ctrl_id: int, module_ref: str, data) -> IoModule:
    module = _get_module(db, ctrl_id, module_ref)
    address = data.address or module.address.lower()
    number = data.number or module.number
    _ensure_free(db, ctrl_id, address, number, module.id)
    new_type = str(data.type) if data.type else str(module.type)
    old_count, new_count = PIN_COUNT[str(module.type)], PIN_COUNT[new_type]
    if new_count < old_count:
        used = _module_pins_used(db, module, from_pin=new_count)
        if used:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                f"Broches {new_count} à {old_count - 1} encore utilisées : {', '.join(used)}.")
        for pin in [p for p in module.pins if int(p.pin_number) >= new_count]:
            db.delete(pin)
    elif new_count > old_count:
        _create_pins(db, module, old_count, new_count)
    firmware_changed = address != module.address.lower() or new_type != str(module.type)
    module.address, module.number, module.type = address, number, new_type
    if firmware_changed:
        _mark_dirty(db, ctrl_id)
    db.commit()
    db.refresh(module)
    return module


def delete_io_module(db: Session, ctrl_id: int, module_ref: str) -> None:
    module = _get_module(db, ctrl_id, module_ref)
    used = _module_pins_used(db, module)
    if used:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Module encore utilisé ({', '.join(used)}) : débranche d'abord ces éléments dans l'appli.")
    db.delete(module)
    _mark_dirty(db, ctrl_id)
    db.commit()


def get_io_modules_for_controller(db: Session, ctrl_id: int):
    return db.query(IoModule).filter(IoModule.controller_id == ctrl_id).order_by(IoModule.number).all()


# --- Flash OTA avec suivi de progression -----------------------------------
#
# Un seul flash à la fois (la compilation ESPHome est lourde) : les demandes
# suivantes attendent leur tour. La progression est tenue en mémoire (pour une
# page rechargée en cours de flash) et diffusée en direct par websocket
# (type FLASH_PROGRESS).

FLASH_STATE: dict[int, dict] = {}
_flash_lock = asyncio.Lock()
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_NINJA_RE = re.compile(r"\[(\d+)/(\d+)\]")
_UPLOAD_RE = re.compile(r"Uploading:.*?(\d{1,3})%")
_PHASES = [
    ("Reading configuration", "Lecture de la configuration", 3),
    ("Generating C++ source", "Génération du programme", 6),
    ("Compiling app", "Compilation", 8),
    ("Successfully compiled program", "Programme compilé", 80),
    ("Connecting to", "Connexion au contrôleur", 82),
    ("Uploading", "Envoi du programme", 83),
    ("OTA successful", "Redémarrage du contrôleur", 99),
]


def flash_in_progress(controller_id: int) -> bool:
    return FLASH_STATE.get(controller_id, {}).get("status") in ("queued", "running")


def flash_states() -> list[dict]:
    """États de flash en cours ou terminés depuis moins de 10 minutes."""
    limit = time.time() - 600
    return [state for state in FLASH_STATE.values() if state["status"] in ("queued", "running") or state["updated"] >= limit]


async def _publish(controller_id: int, controller_name: str, force: bool = False, **fields) -> None:
    state = FLASH_STATE.setdefault(controller_id, {"controller_id": controller_id})
    previous_percent = state.get("percent", 0)
    previous_phase = state.get("phase")
    state.update(fields, controller_name=controller_name, updated=time.time())
    if force or state.get("phase") != previous_phase or state.get("percent", 0) - previous_percent >= 1:
        await ws_manager.broadcast({"type": "FLASH_PROGRESS", **{k: v for k, v in state.items() if k != "updated"}})


def _save_flash_log(controller_id: int, level: str, message: str) -> None:
    with SessionLocal() as db:
        db.add(LogModel(controller_id=controller_id, level=level, component="flash", message=message))
        db.commit()


async def queue_flash(controller_id: int, controller_name: str) -> None:
    """Marque le flash en attente (appelé par la route, avant la tâche de fond)."""
    FLASH_STATE[controller_id] = {"controller_id": controller_id, "started": time.time()}
    await _publish(controller_id, controller_name, force=True, status="queued", phase="En attente", percent=0, error=None)


async def run_esphome_ota(controller_id: int, yaml_content: str, target_ip: str):
    ctrl_name = f"controller_{controller_id}"
    with SessionLocal() as db:
        controller = db.query(Controller).filter(Controller.id == controller_id).first()
        if controller:
            ctrl_name = controller.technical_name

    async with _flash_lock:
        await _publish(controller_id, ctrl_name, force=True, status="running", phase="Préparation", percent=1)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp_file:
            tmp_file.write(yaml_content)
            tmp_path = tmp_file.name

        tail: deque[str] = deque(maxlen=40)
        percent = 1
        phase = "Préparation"
        return_code = -1
        started = time.time()
        try:
            proc = await asyncio.create_subprocess_exec(
                "esphome", "run", tmp_path, "--device", target_ip, "--no-logs",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            buffer = ""
            assert proc.stdout is not None
            while True:
                chunk = await proc.stdout.read(4096)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", "replace")
                *lines, buffer = re.split(r"[\r\n]", buffer)
                for raw_line in lines:
                    line = _ANSI_RE.sub("", raw_line).strip()
                    if not line:
                        continue
                    tail.append(line)
                    for marker, label, value in _PHASES:
                        if marker in line:
                            phase, percent = label, max(percent, value)
                    ninja = _NINJA_RE.search(line)
                    if ninja and phase == "Compilation":
                        done, total = int(ninja.group(1)), int(ninja.group(2))
                        percent = max(percent, 8 + int(72 * done / max(total, 1)))
                    upload = _UPLOAD_RE.search(line)
                    if upload:
                        phase = "Envoi du programme"
                        percent = max(percent, 83 + int(15 * int(upload.group(1)) / 100))
                await _publish(controller_id, ctrl_name, status="running", phase=phase, percent=min(percent, 99))
            return_code = await proc.wait()
        except Exception as e:
            logger.exception("Flash OTA impossible pour %s", ctrl_name)
            tail.append(f"{type(e).__name__} : {e}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        duration = int(time.time() - started)
        with SessionLocal() as db:
            controller = db.query(Controller).filter(Controller.id == controller_id).first()
            if return_code == 0 and controller:
                controller.status = "ONLINE"
                controller.is_dirty = False
                controller.yaml_config = yaml_content
                controller.last_config = yaml_content
                controller.last_sync = datetime.now()
                firmware_flashed(db, controller.id)
            elif controller:
                controller.status = "FLASH_FAILED"
            db.commit()

        if return_code == 0:
            logger.info("Flash OTA réussi pour %s (%s) en %s s", ctrl_name, target_ip, duration)
            _save_flash_log(controller_id, "I", f"Flash réussi en {duration} s")
            await _publish(controller_id, ctrl_name, force=True, status="success", phase="Terminé", percent=100)
            status_value = "ONLINE"
        else:
            error_tail = "\n".join(list(tail)[-15:])
            logger.error("Échec du flash OTA pour %s (code %s) :\n%s", ctrl_name, return_code, error_tail)
            _save_flash_log(controller_id, "E", f"Échec du flash (code {return_code}) :\n{error_tail}")
            await _publish(
                controller_id, ctrl_name, force=True, status="failed", phase="Échec", percent=percent, error=error_tail
            )
            status_value = "FLASH_FAILED"

        await ws_manager.broadcast({
            "type": "CONTROLLER_STATUS",
            "controller_id": controller_id,
            "controller_name": ctrl_name,
            "status": status_value,
        })
