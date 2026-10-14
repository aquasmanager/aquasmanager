from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class EquipmentFaultRead(BaseModel):
    id: int
    controller_id: int
    equipment_id: Optional[int] = None
    code: str
    message: str
    latched: bool
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EquipmentFaultListResponse(BaseModel):
    total: int
    faults: list[EquipmentFaultRead]
