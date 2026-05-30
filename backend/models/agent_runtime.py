from pydantic import BaseModel, Field

from backend.models.agent_tools import MemoryProposalResponse, TaskPreviewResult, TaskDraftResponse
from backend.models.user_planning import UserTaskResponse


class AgentTurnRequest(BaseModel):
    text: str = Field(min_length=1)
    conversation_id: str | None = None


class AgentTurnResponse(BaseModel):
    conversation_id: str
    user_message_id: str
    assistant_message_id: str
    reply: str
    draft: TaskDraftResponse | None = None
    task_preview: TaskPreviewResult | None = None
    confirmed_task: UserTaskResponse | None = None
    memory_proposals: list[MemoryProposalResponse] = Field(default_factory=list)
    requires_user_input: bool = False
    requires_confirmation: bool = False
