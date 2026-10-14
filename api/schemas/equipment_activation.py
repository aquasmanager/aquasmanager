from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class EquipmentActivationRead(BaseModel):
    id: int
    equipment_id: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
