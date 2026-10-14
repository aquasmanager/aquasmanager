from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict

from models.maintenance_task import TaskRecurrence


class MaintenanceTaskCompletionBase(BaseModel):
    completed_at: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=200)


class MaintenanceTaskCompletionCreate(MaintenanceTaskCompletionBase):
    pass


class MaintenanceTaskCompletionRead(BaseModel):
    id: int
    task_id: int
    completed_at: datetime
    note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MaintenanceTaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    recurrence: TaskRecurrence = TaskRecurrence.none
    recurrence_days: Optional[int] = Field(default=None, gt=0)
    next_due_at: Optional[datetime] = None


class MaintenanceTaskCreate(MaintenanceTaskBase):
    aquarium_id: int = Field(gt=0)
    # Aquariums concernés : « single » (aquarium_id), « multiple » (aquarium_ids) ou « all »
    scope: Literal["single", "multiple", "all"] = "single"
    aquarium_ids: list[int] = Field(default_factory=list)


class MaintenanceTaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    recurrence: Optional[TaskRecurrence] = None
    recurrence_days: Optional[int] = Field(default=None, gt=0)
    next_due_at: Optional[datetime] = None
    scope: Optional[Literal["single", "multiple", "all"]] = None
    aquarium_ids: Optional[list[int]] = None


class MaintenanceTaskRead(MaintenanceTaskBase):
    id: int
    aquarium_id: int
    last_completed_at: Optional[datetime] = None
    scope: str = "single"
    aquarium_ids: list[int] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class CalendarEventRead(BaseModel):
    kind: Literal["due", "planned", "done"]
    date: datetime
    task_id: int
    title: str
    aquarium_id: int
    aquarium_name: str
    # Aquariums concernés ([] = tous) : pour filtrer et colorer un élément partagé
    aquarium_ids: list[int] = Field(default_factory=list)
    shared: bool = False
    overdue: bool = False
    note: Optional[str] = None
