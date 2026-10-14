from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class MetricAlertRead(BaseModel):
    id: int
    aquarium_id: int
    source: str
    water_parameter_id: Optional[int] = None
    dashboard_card_id: Optional[int] = None
    maintenance_task_id: Optional[int] = None
    inventory_item_id: Optional[int] = None
    sensor_id: Optional[int] = None
    label: str
    unit: Optional[str] = None
    initial_value: float
    resolved_value: Optional[float] = None
    target_min: Optional[float] = None
    target_max: Optional[float] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    acknowledged: bool = False

    model_config = ConfigDict(from_attributes=True)
