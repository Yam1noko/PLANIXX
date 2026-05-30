from pydantic import BaseModel, Field

from backend.models.scheduling import (
    PlanningRequest,
    PlanningStatus,
    ProfileContext,
    ScheduledTask,
    ScheduleVariant,
    UnscheduledTask,
    Violation,
)


class SolverResultChunk(BaseModel):
    chunk_id: int
    planning_status: PlanningStatus
    profile_context: ProfileContext
    source_request: PlanningRequest | None = None
    schedule_variant: ScheduleVariant
    violations: list[Violation] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class SolverResultChunkingResponse(BaseModel):
    batch_id: str
    total_chunks: int
    chunks: list[SolverResultChunk] = Field(default_factory=list)


class VariantScoreBreakdown(BaseModel):
    variant_id: int
    total_score: float
    completion_score: float
    priority_score: float
    time_preference_score: float
    productivity_score: float
    load_score: float
    focus_structure_score: float
    penalties: float
    mandatory_unscheduled_penalty: float = 0.0
    violation_penalty: float = 0.0
    bad_blocks_count: int = 0
    total_blocks_count: int = 0
    scheduled_tasks_count: int = 0
    unscheduled_tasks_count: int = 0


class BestVariantSelectionResponse(BaseModel):
    batch_id: str
    chunk_id: int
    best_variant_id: int
    selected_chunk: SolverResultChunk
    variant_scores: list[VariantScoreBreakdown] = Field(default_factory=list)


class BestScheduleResponse(BaseModel):
    variant_id: int
    scheduled_tasks: list[ScheduledTask] = Field(default_factory=list)
    unscheduled_tasks: list[UnscheduledTask] = Field(default_factory=list)
