from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.models.user_planning import TimeWindow, UserTaskCreate, UserTaskUpdate, UserTaskResponse


TaskDraftLifecycleStatus = Literal[
    "draft",
    "needs_clarification",
    "validated",
    "preview_ready",
    "confirmed",
    "cancelled",
    "superseded",
]
MemoryCandidateStatus = Literal["pending", "accepted", "rejected"]
IssueSeverity = Literal["info", "warning", "error"]


class TaskDraftInput(UserTaskUpdate):
    raw_text: str = Field(min_length=1)
    conversation_id: str | None = None
    source_message_id: str | None = None
    model_name: str | None = Field(default=None, max_length=100)
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    draft_status: TaskDraftLifecycleStatus | None = None


class TaskDraftPatch(UserTaskUpdate):
    raw_text: str | None = Field(default=None, min_length=1)
    conversation_id: str | None = None
    source_message_id: str | None = None
    model_name: str | None = Field(default=None, max_length=100)
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    draft_status: TaskDraftLifecycleStatus | None = None


class TaskDraftResponse(BaseModel):
    id: str
    user_id: str
    conversation_id: str | None = None
    source_message_id: str | None = None
    status: TaskDraftLifecycleStatus
    raw_text: str
    draft_data: dict = Field(default_factory=dict)
    model_name: str | None = None
    confidence_score: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserTaskPatternResponse(BaseModel):
    id: str
    user_id: str
    pattern_type: str
    name: str
    description: str | None = None
    pattern_data: dict = Field(default_factory=dict)
    confidence_score: float | None = None
    source: str
    is_active: bool
    last_observed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UserMemoryResponse(BaseModel):
    id: str
    user_id: str
    memory_type: str
    content: str
    summary: str | None = None
    memory_data: dict | None = None
    confidence_score: float | None = None
    importance_score: float | None = None
    source: str
    last_accessed_at: datetime | None = None
    superseded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MissingFieldQuestion(BaseModel):
    field: str
    question: str


class TaskDraftValidationResult(BaseModel):
    draft: TaskDraftResponse
    is_valid: bool
    missing_fields: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    normalized_task: dict | None = None


class MissingFieldCheckResult(BaseModel):
    draft: TaskDraftResponse
    missing_fields: list[str] = Field(default_factory=list)
    questions: list[MissingFieldQuestion] = Field(default_factory=list)
    ready_for_validation: bool


class RealismCheckIssue(BaseModel):
    severity: IssueSeverity
    field: str | None = None
    message: str


class RealismCheckResult(BaseModel):
    draft: TaskDraftResponse
    is_realistic: bool
    issues: list[RealismCheckIssue] = Field(default_factory=list)


class TaskPreviewResult(BaseModel):
    draft: TaskDraftResponse
    title: str
    summary: str
    task_payload: dict
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    ready_for_confirmation: bool


class MemoryProposalResponse(BaseModel):
    candidate_id: str
    status: MemoryCandidateStatus
    message: str
    user_confirmation_required: bool
    confirmation_question: str | None = None
    saved_memory_id: str | None = None


class ConfirmedTaskDraftResult(BaseModel):
    draft: TaskDraftResponse
    task: UserTaskResponse


class MemoryProposalInput(BaseModel):
    content: str = Field(min_length=1)
    candidate_type: str = Field(default="preference", min_length=1, max_length=50)
    memory_type: str = Field(default="preference", min_length=1, max_length=50)
    summary: str | None = None
    conversation_id: str | None = None
    source_message_id: str | None = None
    candidate_data: dict | None = None
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    importance_score: float | None = Field(default=None, ge=0, le=1)
    confirm: bool | None = None
    candidate_id: str | None = None


class TaskDraftPreparedData(BaseModel):
    payload: UserTaskCreate
    preview_lines: list[str] = Field(default_factory=list)
    preferred_windows: list[TimeWindow] = Field(default_factory=list)

