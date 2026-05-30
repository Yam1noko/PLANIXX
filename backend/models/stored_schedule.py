from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from backend.models.scheduling import PlanningStatus


class StoredScheduledTaskCreate(BaseModel):
    task_id: str
    start_at: datetime
    end_at: datetime
    variant_id: int | None = 1
    split_part_index: int | None = None
    split_part_count: int | None = None

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_at <= self.start_at:
            raise ValueError("Scheduled task end_at must be greater than start_at")
        return self


class StoredScheduleUpsertRequest(BaseModel):
    planning_start: datetime
    planning_end: datetime
    slot_minutes: int = 15
    status: PlanningStatus = "success"
    selected_variant_id: int | None = 1
    source_request: dict | None = None
    profile_context: dict | None = None
    schedule_metadata: dict | None = None
    scheduled_tasks: list[StoredScheduledTaskCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_range(self):
        if self.planning_end <= self.planning_start:
            raise ValueError("planning_end must be greater than planning_start")
        return self


class StoredScheduledTaskResponse(BaseModel):
    id: str
    schedule_id: str
    task_id: str
    variant_id: int | None = None
    title: str
    start_at: datetime
    end_at: datetime
    duration_minutes: int
    priority: int
    is_mandatory: bool
    split_part_index: int | None = None
    split_part_count: int | None = None
    payload: dict | None = None
    created_at: datetime


class StoredScheduleResponse(BaseModel):
    id: str
    user_id: str
    planning_start: datetime
    planning_end: datetime
    slot_minutes: int
    status: str
    is_current: bool
    selected_variant_id: int | None = None
    source_request: dict | None = None
    profile_context: dict | None = None
    schedule_metadata: dict | None = None
    created_at: datetime
    updated_at: datetime
    scheduled_tasks: list[StoredScheduledTaskResponse] = Field(default_factory=list)
