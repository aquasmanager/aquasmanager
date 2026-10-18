"""
light.py (routes)

Lampes, canaux PWM, programmes horaires, profils, pilotage direct et démo.
Les réglages "vivants" (programme, modes, intensités, plafonds, clair de lune,
acclimatation) sont envoyés à l'ESP par MQTT, sans reflasher ; seuls les
changements de câblage (canaux, broches, inversion, fréquence) le demandent.
"""

import logging
from datetime import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from middleware.auth import min_role_required
from middleware.database import get_db
from models.controller import Controller
from models.controller_pin import ControllerPin
from models.light import Light
from models.light_channel import ChannelMode, LightChannel
from models.light_schedule import LightSchedule
from schemas.light import (
    LightCatalogRead,
    LightChannelCreate,
    LightChannelUpdate,
    LightControl,
    LightCreate,
    LightDemo,
    LightDemoRead,
    LightProfileApply,
    LightRead,
    LightScheduleCopy,
    LightUpdate,
    SchedulePoint,
)
from services.light_control import (
    MAX_SCHEDULE_POINTS,
    acclimation_percent,
    channel_points,
    publish_channel_states,
    publish_demo,
    publish_schedule,
)
from services.light_profiles import (
    DEFAULT_MOONLIGHT_INTENSITY,
    MOONLIGHT_SPECTRA,
    PROFILES,
    SPECTRA,
    profile_bounds,
    shifted_curves,
)
from services.esphome_generator import TIMEZONE
from services.naming import ensure_unique_light_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lights", tags=["lights"], dependencies=[Depends(min_role_required("consult"))])

# ESP32 : 16 canaux LEDC ; GPIO 34-39 en entrée seule, incapables de PWM
MAX_PWM_CHANNELS_PER_CONTROLLER = 16
ESP32_INPUT_ONLY_PINS = range(34, 40)
# Réglages qui changent le firmware (les autres passent par MQTT)
_WIRING_LIGHT_FIELDS = {"controller_id", "pwm_frequency"}
_WIRING_CHANNEL_FIELDS = {"pin_id", "inverted"}


# --- Helpers ---

def _get_light(db: Session, light_id: int) -> Light:
    light = db.query(Light).filter(Light.id == light_id).first()
    if not light:
        raise HTTPException(status_code=404, detail="Lumière non trouvée")
    return light


def _get_channel(db: Session, channel_id: int) -> LightChannel:
    channel = db.query(LightChannel).filter(LightChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Canal non trouvé")
    return channel


def _read_light(light: Light) -> dict:
    return {
        "id": light.id,
        "name": light.name,
        "aquarium_id": light.aquarium_id,
        "controller_id": light.controller_id,
        "pwm_frequency": light.pwm_frequency,
        "moonlight": [
            {"channel_id": ch.id, "intensity": ch.moonlight_intensity}
            for ch in light.light_channels
            if ch.moonlight_intensity
        ],
        "acclimation_start": light.acclimation_start,
        "acclimation_days": light.acclimation_days,
        "acclimation_start_percent": light.acclimation_start_percent,
        "acclimation_percent": acclimation_percent(light),
        "channels": [
            {
                "id": ch.id,
                "light_id": ch.light_id,
                "name": ch.name,
                "pin_id": ch.pin_id,
                "pin_number": ch.pin.pin_number if ch.pin else None,
                "color": ch.color,
                "spectrum": ch.spectrum,
                "mode": ch.mode,
                "max_intensity": ch.max_intensity,
                "min_intensity": ch.min_intensity,
                "current_intensity": ch.current_intensity,
                "inverted": ch.inverted,
                "moonlight_intensity": ch.moonlight_intensity,
                "schedule": [{"minute": m, "intensity": v} for m, v in channel_points(ch)],
            }
            for ch in light.light_channels
        ],
    }


def _mark_dirty(db: Session, controller_id: Optional[int]) -> None:
    if controller_id:
        db.query(Controller).filter(Controller.id == controller_id).update({Controller.is_dirty: True})


def _require_rtc(db: Session, controller_id: int) -> None:
    controller = db.query(Controller).filter(Controller.id == controller_id).first()
    if controller is None:
        raise HTTPException(status_code=404, detail="Contrôleur non trouvé")
    if not controller.rtc_model:
        raise HTTPException(
            status_code=400,
            detail="Ce contrôleur n'a pas d'horloge RTC : ajoute-la d'abord (Contrôleurs > Modules d'extension), "
                   "le programme des lumières en dépend.",
        )


def _validate_pwm_pin(db: Session, light: Light, pin_id: int, channel_id: Optional[int] = None) -> ControllerPin:
    pin = db.query(ControllerPin).filter(ControllerPin.id == pin_id).first()
    if not pin or pin.controller_id != light.controller_id:
        raise HTTPException(status_code=400, detail="Cette broche n'appartient pas au contrôleur de la lampe.")
    module_type = str(getattr(pin.io_module.type, "value", pin.io_module.type)) if pin.io_module else None
    if pin.module_id is not None and module_type != "PCA9685":
        raise HTTPException(
            status_code=400,
            detail="Ce module ne sait pas faire de PWM : choisis une broche de l'ESP ou un canal de module PCA9685.",
        )
    if pin.module_id is None and pin.pin_number.isdigit() and int(pin.pin_number) in ESP32_INPUT_ONLY_PINS:
        raise HTTPException(status_code=400, detail=f"GPIO {pin.pin_number} est en entrée seule : impossible d'y faire du PWM.")
    owner = pin.lights_channel
    if owner is not None and owner.id != channel_id:
        raise HTTPException(status_code=409, detail=f"Broche déjà utilisée par le canal « {owner.name} ».")
    mode = pin.mode.value if hasattr(pin.mode, "value") else str(pin.mode)
    if owner is None and mode != "FREE":
        raise HTTPException(status_code=409, detail="Cette broche est déjà utilisée par un autre équipement ou capteur.")
    return pin


def _claim_pin(pin: ControllerPin, channel_name: str) -> None:
    pin.bus = "PWM"
    pin.mode = "OUT"
    pin.label = channel_name


def _release_pin(pin: Optional[ControllerPin]) -> None:
    if pin is not None:
        pin.bus = "FREE"
        pin.mode = "FREE"
        pin.label = "FREE"


def _set_schedule(channel: LightChannel, points: list[tuple[int, int]]) -> None:
    channel.schedules.clear()
    for minute, intensity in sorted(dict(points).items())[:MAX_SCHEDULE_POINTS]:
        channel.schedules.append(
            LightSchedule(schedule_time=time(minute // 60, minute % 60), intensity=intensity)
        )


# --- Catalogue ---

@router.get("/catalog", response_model=LightCatalogRead)
def get_light_catalog():
    return {
        "spectra": [{"key": k, "label": s.label, "color": s.color} for k, s in SPECTRA.items()],
        "profiles": [
            {"key": k, "label": p.label, "description": p.description,
             "start": profile_bounds(p)[0], "end": profile_bounds(p)[1]}
            for k, p in PROFILES.items()
        ],
        "timezone": TIMEZONE,
    }


# --- Lampes ---

@router.get("/", response_model=List[LightRead])
def list_lights(aquarium_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    query = db.query(Light)
    if aquarium_id is not None:
        query = query.filter(Light.aquarium_id == aquarium_id)
    return [_read_light(light) for light in query.order_by(Light.name).all()]


@router.get("/{light_id}", response_model=LightRead)
def get_light(light_id: int, db: Session = Depends(get_db)):
    return _read_light(_get_light(db, light_id))


@router.post("/", response_model=LightRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(min_role_required("user"))])
def create_light(light_in: LightCreate, db: Session = Depends(get_db)):
    ensure_unique_light_name(db, light_in.name, light_in.aquarium_id)
    _require_rtc(db, light_in.controller_id)
    light = Light(**light_in.model_dump())
    db.add(light)
    db.commit()
    db.refresh(light)
    return _read_light(light)


@router.patch("/{light_id}", response_model=LightRead, dependencies=[Depends(min_role_required("user"))])
def update_light(light_id: int, update: LightUpdate, db: Session = Depends(get_db)):
    light = _get_light(db, light_id)
    data = update.model_dump(exclude_unset=True)
    moonlight = data.pop("moonlight", None)
    if moonlight is not None:
        values = {m["channel_id"]: m["intensity"] for m in moonlight}
        if not set(values) <= {ch.id for ch in light.light_channels}:
            raise HTTPException(status_code=400, detail="Les canaux du clair de lune doivent appartenir à cette lampe.")
        for ch in light.light_channels:
            ch.moonlight_intensity = values.get(ch.id, 0)
    if "controller_id" in data and data["controller_id"] != light.controller_id and light.light_channels:
        raise HTTPException(status_code=400, detail="Supprime d'abord les canaux avant de changer de contrôleur.")
    if "controller_id" in data and data["controller_id"] != light.controller_id:
        _require_rtc(db, data["controller_id"])
    if (data.get("name") and data["name"] != light.name) or data.get("aquarium_id", light.aquarium_id) != light.aquarium_id:
        ensure_unique_light_name(db, data.get("name") or light.name, data.get("aquarium_id", light.aquarium_id), light.id)

    wiring_changed = any(k in data and data[k] != getattr(light, k) for k in _WIRING_LIGHT_FIELDS)
    old_controller = light.controller_id
    for field, value in data.items():
        setattr(light, field, value)
    if wiring_changed:
        _mark_dirty(db, old_controller)
        _mark_dirty(db, light.controller_id)
    db.commit()
    db.refresh(light)
    publish_channel_states(light)
    return _read_light(light)


@router.delete("/{light_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(min_role_required("manager"))])
def delete_light(light_id: int, db: Session = Depends(get_db)):
    light = _get_light(db, light_id)
    for channel in light.light_channels:
        _release_pin(channel.pin)
    _mark_dirty(db, light.controller_id)
    db.delete(light)
    db.commit()


# --- Canaux ---

@router.post("/{light_id}/channels", response_model=LightRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(min_role_required("user"))])
def create_channel(light_id: int, channel_in: LightChannelCreate, db: Session = Depends(get_db)):
    light = _get_light(db, light_id)
    _require_rtc(db, light.controller_id)
    used = (
        db.query(LightChannel).join(Light, Light.id == LightChannel.light_id)
        .filter(Light.controller_id == light.controller_id).count()
    )
    if used >= MAX_PWM_CHANNELS_PER_CONTROLLER:
        raise HTTPException(status_code=400, detail=f"Un ESP32 gère au plus {MAX_PWM_CHANNELS_PER_CONTROLLER} canaux PWM.")
    if channel_in.spectrum not in SPECTRA:
        raise HTTPException(status_code=400, detail="Spectre inconnu.")
    pin = _validate_pwm_pin(db, light, channel_in.pin_id)
    channel = LightChannel(**channel_in.model_dump(), light_id=light.id, mode=ChannelMode.AUTO)
    db.add(channel)
    _claim_pin(pin, channel.name)
    _mark_dirty(db, light.controller_id)
    db.commit()
    db.refresh(light)
    return _read_light(light)


@router.patch("/channels/{channel_id}", response_model=LightRead, dependencies=[Depends(min_role_required("user"))])
def update_channel(channel_id: int, update: LightChannelUpdate, db: Session = Depends(get_db)):
    channel = _get_channel(db, channel_id)
    light = channel.light
    data = update.model_dump(exclude_unset=True)
    if "spectrum" in data and data["spectrum"] not in SPECTRA:
        raise HTTPException(status_code=400, detail="Spectre inconnu.")
    if "pin_id" in data and data["pin_id"] != channel.pin_id:
        new_pin = _validate_pwm_pin(db, light, data["pin_id"], channel.id)
        _release_pin(channel.pin)
        _claim_pin(new_pin, data.get("name", channel.name))
    wiring_changed = any(k in data and data[k] != getattr(channel, k) for k in _WIRING_CHANNEL_FIELDS)
    if data.get("min_intensity", channel.min_intensity) > data.get("max_intensity", channel.max_intensity):
        raise HTTPException(status_code=400, detail="Le seuil d'allumage dépasse le plafond du canal.")
    for field, value in data.items():
        setattr(channel, field, value)
    if wiring_changed:
        _mark_dirty(db, light.controller_id)
    db.commit()
    db.refresh(light)
    publish_channel_states(light)
    return _read_light(light)


@router.delete("/channels/{channel_id}", response_model=LightRead, dependencies=[Depends(min_role_required("user"))])
def delete_channel(channel_id: int, db: Session = Depends(get_db)):
    channel = _get_channel(db, channel_id)
    light = channel.light
    _release_pin(channel.pin)
    db.delete(channel)
    _mark_dirty(db, light.controller_id)
    db.commit()
    db.refresh(light)
    return _read_light(light)


# --- Programme ---

@router.put("/channels/{channel_id}/schedule", response_model=LightRead,
            dependencies=[Depends(min_role_required("user"))])
def set_channel_schedule(channel_id: int, points: List[SchedulePoint], db: Session = Depends(get_db)):
    if len(points) > MAX_SCHEDULE_POINTS:
        raise HTTPException(status_code=400, detail=f"{MAX_SCHEDULE_POINTS} points maximum par canal.")
    channel = _get_channel(db, channel_id)
    _set_schedule(channel, [(p.minute, p.intensity) for p in points])
    db.commit()
    light = channel.light
    db.refresh(light)
    publish_schedule(light)
    return _read_light(light)


@router.post("/{light_id}/copy-schedule", response_model=LightRead, dependencies=[Depends(min_role_required("user"))])
def copy_schedule(light_id: int, request: LightScheduleCopy, db: Session = Depends(get_db)):
    light = _get_light(db, light_id)
    channels = {ch.id: ch for ch in light.light_channels}
    if request.source_channel_id not in channels or any(t not in channels for t in request.target_channel_ids):
        raise HTTPException(status_code=400, detail="Les canaux doivent appartenir à cette lampe.")
    points = channel_points(channels[request.source_channel_id])
    for target_id in request.target_channel_ids:
        if target_id != request.source_channel_id:
            _set_schedule(channels[target_id], points)
    db.commit()
    db.refresh(light)
    publish_schedule(light)
    return _read_light(light)


@router.post("/{light_id}/apply-profile", response_model=LightRead, dependencies=[Depends(min_role_required("user"))])
def apply_profile(light_id: int, request: LightProfileApply, db: Session = Depends(get_db)):
    light = _get_light(db, light_id)
    profile = PROFILES.get(request.profile)
    if profile is None:
        raise HTTPException(status_code=400, detail="Profil inconnu.")
    curves = shifted_curves(profile, request.start)
    for channel in light.light_channels:
        _set_schedule(channel, curves.get(channel.spectrum, []))
        channel.mode = ChannelMode.AUTO
    if request.moonlight and not any(ch.moonlight_intensity for ch in light.light_channels):
        moon = next((ch for s in MOONLIGHT_SPECTRA for ch in light.light_channels if ch.spectrum == s), None)
        if moon is not None:
            moon.moonlight_intensity = DEFAULT_MOONLIGHT_INTENSITY
    db.commit()
    db.refresh(light)
    publish_schedule(light)
    publish_channel_states(light)
    return _read_light(light)


# --- Pilotage direct ---

@router.post("/{light_id}/control", response_model=LightRead, dependencies=[Depends(min_role_required("user"))])
def control_light(light_id: int, command: LightControl, db: Session = Depends(get_db)):
    light = _get_light(db, light_id)
    targets = [ch for ch in light.light_channels if command.channel_id is None or ch.id == command.channel_id]
    if not targets:
        raise HTTPException(status_code=404, detail="Canal non trouvé")
    for channel in targets:
        channel.mode = command.mode
        if command.value is not None:
            channel.current_intensity = command.value
    db.commit()
    db.refresh(light)
    publish_channel_states(light)
    return _read_light(light)


@router.post("/{light_id}/demo", response_model=LightDemoRead, dependencies=[Depends(min_role_required("user"))])
def start_demo(light_id: int, request: LightDemo, db: Session = Depends(get_db)):
    light = _get_light(db, light_id)
    publish_schedule(light)
    publish_demo(light, request.duration_s)
    return {"light_id": light.id, "duration_s": request.duration_s, "status": "started"}


@router.delete("/{light_id}/demo", response_model=LightDemoRead, dependencies=[Depends(min_role_required("user"))])
def stop_demo(light_id: int, db: Session = Depends(get_db)):
    light = _get_light(db, light_id)
    publish_demo(light, None)
    return {"light_id": light.id, "status": "stopped"}
