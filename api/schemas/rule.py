from datetime import time
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

ConditionType = Literal["SENSOR_STATE", "THRESHOLD", "TIME_RANGE"]
ThresholdOperator = Literal[">", ">=", "<", "<="]


class RuleConditionCreate(BaseModel):
    """
    SENSOR_STATE : capteur tout-ou-rien (niveau) dans l'état trigger_state.
    THRESHOLD : capteur numérique (température) comparé à threshold_value.
    TIME_RANGE : heure courante entre start_time (inclus) et end_time (exclu),
    la plage pouvant passer minuit (22:00 -> 07:00).
    """

    condition_type: ConditionType = "SENSOR_STATE"
    sensor_id: Optional[int] = None
    trigger_state: Optional[str] = None
    operator: Optional[ThresholdOperator] = None
    threshold_value: Optional[float] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None

    @model_validator(mode="after")
    def check_fields(self):
        if self.condition_type == "TIME_RANGE":
            if self.start_time is None or self.end_time is None:
                raise ValueError("Une plage horaire demande une heure de début et de fin.")
            if self.start_time == self.end_time:
                raise ValueError("L'heure de début et de fin doivent être différentes.")
            self.sensor_id = self.trigger_state = self.operator = self.threshold_value = None
            return self
        if self.sensor_id is None:
            raise ValueError("Cette condition demande un capteur.")
        self.start_time = self.end_time = None
        if self.condition_type == "THRESHOLD":
            if self.operator is None or self.threshold_value is None:
                raise ValueError("Une condition de seuil demande un opérateur et une valeur.")
            self.trigger_state = None
        else:
            if not self.trigger_state:
                raise ValueError("Une condition d'état demande l'état attendu (LOW ou HIGH).")
            self.operator = None
            self.threshold_value = None
        return self


class RuleConditionRead(RuleConditionCreate):
    id: int
    rule_id: int

    model_config = ConfigDict(from_attributes=True)


class RuleCreate(BaseModel):
    name: str = Field(min_length=1)
    match_type: Literal["AND", "OR"] = "AND"
    equipment_id: int | None = None
    group_id: int | None = None
    action: Literal["ON", "OFF", "NOTIFY"]
    is_active: bool = True
    is_safety_lock: bool = False
    revert_on_exit: bool = False
    max_duration_seconds: Optional[int] = Field(default=None, gt=0)
    notification_channel: Optional[str] = None
    notification_message: Optional[str] = Field(default=None, max_length=200)
    conditions: list[RuleConditionCreate] = Field(min_length=1)


class RuleRead(BaseModel):
    id: int
    name: str
    match_type: str
    equipment_id: int | None = None
    group_id: int | None = None
    action: str
    is_active: bool
    is_safety_lock: bool
    revert_on_exit: bool = False
    max_duration_seconds: Optional[int] = None
    notification_channel: Optional[str] = None
    notification_message: Optional[str] = None
    conditions: list[RuleConditionRead]

    model_config = ConfigDict(from_attributes=True)


class RuleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    match_type: Optional[Literal["AND", "OR"]] = None
    equipment_id: Optional[int] = None
    group_id: Optional[int] = None
    action: Optional[Literal["ON", "OFF", "NOTIFY"]] = None
    notification_channel: Optional[str] = None
    notification_message: Optional[str] = Field(default=None, max_length=200)
    max_duration_seconds: Optional[int] = Field(default=None, gt=0)
    is_active: Optional[bool] = None
    is_safety_lock: Optional[bool] = None
    revert_on_exit: Optional[bool] = None
    conditions: Optional[List[RuleConditionCreate]] = Field(default=None, min_length=1)
