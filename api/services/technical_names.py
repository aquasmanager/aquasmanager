"""
Noms techniques des équipements et capteurs : identifiants du firmware ESPHome
et des topics MQTT (aquarium/<contrôleur>/switch/<nom technique>/...).

Format : <nom>_<aquarium>, ex. « osmolateur_recif » ; uniques pour tous les
équipements et capteurs (suffixe _2, _3... en cas de collision). Recalculés
quand le nom ou l'aquarium change.

Le firmware flashé connaît encore l'ancien nom jusqu'au flash suivant :
deployed_technical_name le garde, pour reconnaître ses messages et lui envoyer
les commandes sur ses topics (firmware_name). Le flash le vide.
"""

import re
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.aquarium import Aquarium
from models.equipment import Equipment
from models.sensor import Sensor

TECHNICAL_NAME_MAX = 30
# Partie « aquarium » gardée au moins à cette longueur si le nom est long
AQUARIUM_PART_MIN = 8

_ACCENTS = str.maketrans("éèêëàâäùûüôöîïçñ", "eeeeaaauuuooiicn")


def slugify(text: str) -> str:
    slug = (text or "").lower().translate(_ACCENTS)
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", slug)).strip("_")


def base_name(name: str, aquarium_name: Optional[str]) -> str:
    """« Osmolateur » + « Récif » -> « osmolateur_recif » (30 caractères au plus)."""
    name_part = slugify(name) or "element"
    aquarium_part = slugify(aquarium_name or "")
    if not aquarium_part or name_part == aquarium_part or name_part.endswith(f"_{aquarium_part}"):
        return name_part[:TECHNICAL_NAME_MAX].strip("_")
    room = TECHNICAL_NAME_MAX - 1 - len(aquarium_part)
    if len(name_part) > room:
        aquarium_part = aquarium_part[: max(AQUARIUM_PART_MIN, room if room > 0 else 0)].strip("_")
        name_part = name_part[: TECHNICAL_NAME_MAX - 1 - len(aquarium_part)].strip("_")
    # Le firmware exige un identifiant commençant par une lettre
    result = f"{name_part}_{aquarium_part}"
    return result if result[0].isalpha() else f"e_{result}"[:TECHNICAL_NAME_MAX]


def firmware_name(entity) -> str:
    """Nom sous lequel le firmware flashé connaît l'équipement ou le capteur."""
    return entity.deployed_technical_name or entity.technical_name


def firmware_name_column(model):
    return func.coalesce(model.deployed_technical_name, model.technical_name)


def _taken(db: Session, candidate: str, entity_type: str, entity_id: Optional[int]) -> bool:
    for model, kind in ((Sensor, "sensor"), (Equipment, "equipment")):
        query = db.query(model.id).filter(
            (model.technical_name == candidate) | (model.deployed_technical_name == candidate)
        )
        for (other_id,) in query:
            if entity_type != kind or other_id != entity_id:
                return True
    return False


def unique_technical_name(db: Session, base: str, entity_type: str, entity_id: Optional[int] = None) -> str:
    """base, sinon base_2, base_3... (y compris parmi les noms encore flashés)."""
    base = (base or "element")[:TECHNICAL_NAME_MAX].strip("_") or "element"
    candidate, n = base, 1
    while _taken(db, candidate, entity_type, entity_id):
        n += 1
        suffix = f"_{n}"
        candidate = base[: TECHNICAL_NAME_MAX - len(suffix)].rstrip("_") + suffix
    return candidate


def technical_name_for(
    db: Session, name: str, aquarium_id: Optional[int], entity_type: str, entity_id: Optional[int] = None
) -> str:
    aquarium = db.get(Aquarium, aquarium_id) if aquarium_id else None
    return unique_technical_name(db, base_name(name, aquarium.name if aquarium else None), entity_type, entity_id)


def rename(db: Session, entity, entity_type: str) -> bool:
    """Recalcule le nom technique (nom ou aquarium changé). Garde le nom du firmware
    flashé pour la transition. Retourne True si le nom a changé."""
    new_name = technical_name_for(db, entity.name, entity.aquarium_id, entity_type, entity.id)
    if new_name == entity.technical_name:
        return False
    if entity.deployed_technical_name is None:
        entity.deployed_technical_name = entity.technical_name
    elif entity.deployed_technical_name == new_name:
        entity.deployed_technical_name = None  # retour au nom flashé
    entity.technical_name = new_name
    return True


def firmware_flashed(db: Session, controller_id: int) -> None:
    """Après un flash : le firmware utilise désormais les noms techniques actuels."""
    for model in (Equipment, Sensor):
        db.query(model).filter(model.controller_id == controller_id, model.deployed_technical_name.isnot(None)).update(
            {model.deployed_technical_name: None}, synchronize_session=False
        )
