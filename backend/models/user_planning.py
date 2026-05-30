from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.domain.scheduling.availability_recurrence import (
    normalize_availability_recurrence_rule,
)
from backend.models.personalization import UserPreferenceProfile
from backend.models.scheduling import EnergyRequired, PlanningResult, SchedulerSettings, TimeWindow


TaskStatus = Literal["active", "completed", "cancelled", "archived"]


class UserTaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    duration_minutes: int = Field(gt=0)
    priority: int = Field(ge=1, le=5)
    category: str | None = Field(default=None, max_length=50)
    energy_required: EnergyRequired | None = None
    status: TaskStatus = "active"
    deadline: datetime | None = None
    earliest_start: datetime | None = None
    latest_end: datetime | None = None
    fixed_start: datetime | None = None
    is_mandatory: bool = False
    is_fixed: bool = False
    allow_splitting: bool = False
    min_split_part_minutes: int | None = Field(default=None, gt=0)
    preferred_windows: list[TimeWindow] = Field(default_factory=list)
    allowed_windows: list[TimeWindow] = Field(default_factory=list)
    constraints: dict | None = None
    llm_metadata: dict | None = None

    @model_validator(mode="after")
    def validate_fixed_task(self):
        if self.is_fixed and self.fixed_start is None:
            raise ValueError("fixed_start is required when is_fixed=true")
        if self.is_fixed and self.allow_splitting:
            raise ValueError("fixed tasks cannot be split")
        if self.allow_splitting and self.min_split_part_minutes is None:
            raise ValueError(
                "min_split_part_minutes is required when allow_splitting=true"
            )
        return self


class UserTaskCreate(UserTaskBase):
    id: str | None = Field(default=None, max_length=255)


class UserTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    priority: int | None = Field(default=None, ge=1, le=5)
    category: str | None = Field(default=None, max_length=50)
    energy_required: EnergyRequired | None = None
    status: TaskStatus | None = None
    deadline: datetime | None = None
    earliest_start: datetime | None = None
    latest_end: datetime | None = None
    fixed_start: datetime | None = None
    is_mandatory: bool | None = None
    is_fixed: bool | None = None
    allow_splitting: bool | None = None
    min_split_part_minutes: int | None = Field(default=None, gt=0)
    preferred_windows: list[TimeWindow] | None = None
    allowed_windows: list[TimeWindow] | None = None
    constraints: dict | None = None
    llm_metadata: dict | None = None


class UserTaskResponse(UserTaskBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AvailabilityWindowBase(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    start: datetime
    end: datetime
    is_recurring: bool = False
    recurrence_rule: str | None = Field(default=None, max_length=255)
    source: str = Field(default="manual", max_length=50)

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, data):
        if not isinstance(data, dict):
            return data

        normalized = data.copy()
        normalized["title"] = None
        normalized["recurrence_rule"] = normalize_availability_recurrence_rule(
            normalized.get("recurrence_rule")
        )
        if normalized.get("recurrence_rule") is not None:
            normalized["is_recurring"] = True
        return normalized

    @model_validator(mode="after")
    def validate_range(self):
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        if self.is_recurring and self.recurrence_rule is None:
            raise ValueError("recurrence_rule is required when is_recurring=true")
        if not self.is_recurring:
            self.recurrence_rule = None
        return self


class AvailabilityWindowCreate(AvailabilityWindowBase):
    pass


class AvailabilityWindowUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    start: datetime | None = None
    end: datetime | None = None
    is_recurring: bool | None = None
    recurrence_rule: str | None = Field(default=None, max_length=255)
    source: str | None = Field(default=None, max_length=50)

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, data):
        if not isinstance(data, dict):
            return data

        normalized = data.copy()
        if "title" in normalized:
            normalized["title"] = None
        if "recurrence_rule" in normalized:
            normalized["recurrence_rule"] = normalize_availability_recurrence_rule(
                normalized.get("recurrence_rule")
            )
        if normalized.get("recurrence_rule") is not None:
            normalized["is_recurring"] = True
        return normalized

    @model_validator(mode="after")
    def validate_range(self):
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self


class AvailabilityWindowResponse(AvailabilityWindowBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime


class UserBusyIntervalBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    start: datetime
    end: datetime
    source: str = Field(default="manual", max_length=50)
    external_event_id: str | None = Field(default=None, max_length=255)
    payload: dict | None = None

    @model_validator(mode="after")
    def validate_range(self):
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self


class UserBusyIntervalCreate(UserBusyIntervalBase):
    pass


class UserBusyIntervalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    start: datetime | None = None
    end: datetime | None = None
    source: str | None = Field(default=None, max_length=50)
    external_event_id: str | None = Field(default=None, max_length=255)
    payload: dict | None = None

    @model_validator(mode="after")
    def validate_range(self):
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self


class UserBusyIntervalResponse(UserBusyIntervalBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime


class StoredPlanningRunRequest(BaseModel):
    planning_start: datetime
    planning_end: datetime
    slot_minutes: int = 15
    task_statuses: list[TaskStatus] = Field(default_factory=lambda: ["active"])
    settings: SchedulerSettings = Field(default_factory=SchedulerSettings)

    @model_validator(mode="after")
    def validate_range(self):
        if self.planning_end <= self.planning_start:
            raise ValueError("planning_end must be greater than planning_start")
        return self


class PlanningContextResponse(BaseModel):
    user_id: str
    profile: UserPreferenceProfile
    tasks: list[UserTaskResponse] = Field(default_factory=list)
    availability_windows: list[AvailabilityWindowResponse] = Field(default_factory=list)
    busy_intervals: list[UserBusyIntervalResponse] = Field(default_factory=list)


class StoredPlanningPreviewResponse(BaseModel):
    planning_request: dict
    planning_result: PlanningResult
