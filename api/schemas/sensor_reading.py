from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional, List


class SensorReadingBase(BaseModel):
    sensor_id: int
    value: float
    timestamp: datetime

class SensorReadingCreate(SensorReadingBase):
    pass

class SensorReadingUpdate(SensorReadingBase):
    sensor_id: Optional[int] = None
    value: Optional[float] = None
    timestamp: Optional[datetime] = None


class SensorReadingRead(SensorReadingBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class SensorReadingListResponse(BaseModel):
    total: int
    sensors_reading: List[SensorReadingRead]
