from pydantic import BaseModel, ConfigDict
from typing import List

from models.equipment import EquipmentMode

# Schéma simple pour un équipement dans le groupe (pour l'affichage)
class EquipmentInGroup(BaseModel):
    id: int
    name: str
    status: str
    mode: str

    model_config = ConfigDict(from_attributes=True)

class GroupControlModeRequest(BaseModel):
    mode: EquipmentMode

# Schéma pour créer un groupe (avec optionnellement la liste des IDs d'équipements à lier tout de suite)
class EquipmentGroupCreate(BaseModel):
    name: str
    equipment_ids: List[int] = []

# Schéma pour mettre à jour un groupe
class EquipmentGroupUpdate(BaseModel):
    name: str | None = None
    equipment_ids: List[int] | None = None

class GroupCommandPayload(BaseModel):
    command: str

# Schéma complet renvoyé par l'API (Lecture)
class EquipmentGroupResponse(BaseModel):
    id: int
    name: str
    equipments: List[EquipmentInGroup] = []

    model_config = ConfigDict(from_attributes=True)