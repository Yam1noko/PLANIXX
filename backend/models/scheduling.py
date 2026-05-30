from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from backend.models.personalization import UserPreferenceProfile


EnergyRequired = Literal["low", "medium", "high"]
PlanningStatus = Literal["success", "partial"]
SchedulerMode = Literal["full", "quick"]


class TimeWindow(BaseModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_range(self):
        if self.end <= self.start:
            raise ValueError("Window end must be greater than start")
        return self


class BusyInterval(BaseModel):
    title: str
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_range(self):
        if self.end <= self.start:
            raise ValueError("Busy interval end must be greater than start")
        return self


class SchedulerSettings(BaseModel):
    mode: SchedulerMode = "full"
    min_break_minutes: int = 0
    max_daily_planned_minutes: int | None = 480
    max_schedule_variants: int = Field(default=10, ge=1, le=10)
    use_warm_start: bool = False
    replan_from_current_schedule: bool = False


class TaskPlacementHint(BaseModel):
    task_id: str
    start: datetime
    split_part_index: int | None = None
    split_part_count: int | None = None


class TaskInput(BaseModel):
    id: str
    title: str
    duration_minutes: int = Field(gt=0)
    priority: int = Field(ge=1, le=5)

    deadline: datetime | None = None
    earliest_start: datetime | None = None
    latest_end: datetime | None = None

    preferred_windows: list[TimeWindow] = Field(default_factory=list)
    allowed_windows: list[TimeWindow] = Field(default_factory=list)

    is_fixed: bool = False
    fixed_start: datetime | None = None

    is_mandatory: bool = False
    allow_splitting: bool = False
    min_split_part_minutes: int | None = Field(default=None, gt=0)

    category: str | None = None
    energy_required: EnergyRequired | None = None

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


class PlanningRequest(BaseModel):
    user_id: str | None = None

    planning_start: datetime
    planning_end: datetime
    slot_minutes: int = 15

    tasks: list[TaskInput]
    busy_intervals: list[BusyInterval] = Field(default_factory=list)
    available_windows: list[TimeWindow] = Field(default_factory=list)
    placement_hints: list[TaskPlacementHint] = Field(default_factory=list)
    settings: SchedulerSettings = Field(default_factory=SchedulerSettings)

    @model_validator(mode="after")
    def validate_request(self):
        if self.planning_end <= self.planning_start:
            raise ValueError("planning_end must be greater than planning_start")

        if self.slot_minutes <= 0:
            raise ValueError("slot_minutes must be greater than 0")

        ids = [task.id for task in self.tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("Task IDs must be unique")

        if not _is_offset_aligned(
            self.planning_start,
            self.planning_end,
            self.slot_minutes,
        ):
            raise ValueError("planning_end must align with slot_minutes")

        for task in self.tasks:
            if task.duration_minutes % self.slot_minutes != 0:
                raise ValueError(
                    f"Task '{task.id}' duration_minutes must align with slot_minutes"
                )

            if (
                task.allow_splitting
                and task.min_split_part_minutes % self.slot_minutes != 0
            ):
                raise ValueError(
                    f"Task '{task.id}' min_split_part_minutes must align with slot_minutes"
                )

            if task.fixed_start and not _is_offset_aligned(
                self.planning_start,
                task.fixed_start,
                self.slot_minutes,
            ):
                raise ValueError(
                    f"Task '{task.id}' fixed_start must align with slot_minutes"
                )

        for interval in self.busy_intervals:
            if not _is_offset_aligned(
                self.planning_start,
                interval.start,
                self.slot_minutes,
            ):
                raise ValueError(
                    f"Busy interval '{interval.title}' start must align with slot_minutes"
                )

            if not _is_offset_aligned(
                self.planning_start,
                interval.end,
                self.slot_minutes,
            ):
                raise ValueError(
                    f"Busy interval '{interval.title}' end must align with slot_minutes"
                )

        return self


class ScheduledTask(BaseModel):
    task_id: str
    title: str
    task: TaskInput
    start: datetime
    end: datetime
    duration_minutes: int
    priority: int
    is_mandatory: bool
    split_part_index: int | None = None
    split_part_count: int | None = None


class UnscheduledTask(BaseModel):
    task_id: str
    title: str
    task: TaskInput
    reason: str


class Violation(BaseModel):
    code: str
    message: str


class ProfileContext(BaseModel):
    user_id: str | None = None
    profile_used: bool = False
    profile: UserPreferenceProfile | None = None


class ScheduleVariant(BaseModel):
    variant_id: int
    scheduled_tasks: list[ScheduledTask] = Field(default_factory=list)
    unscheduled_tasks: list[UnscheduledTask] = Field(default_factory=list)
    score: float | None = None
    metadata: dict = Field(default_factory=dict)


class PlanningResult(BaseModel):
    status: PlanningStatus
    scheduled_tasks: list[ScheduledTask] = Field(default_factory=list)
    unscheduled_tasks: list[UnscheduledTask] = Field(default_factory=list)
    schedule_variants: list[ScheduleVariant] = Field(default_factory=list)
    violations: list[Violation] = Field(default_factory=list)
    source_request: PlanningRequest | None = None
    profile_context: ProfileContext = Field(default_factory=ProfileContext)
    metadata: dict = Field(default_factory=dict)


def _is_offset_aligned(
    start: datetime,
    value: datetime,
    slot_minutes: int,
) -> bool:
    return (value - start).total_seconds() % (slot_minutes * 60) == 0
