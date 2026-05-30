from fastapi import APIRouter, Depends, Query, status

from backend.api.dependencies.auth import ensure_user_access, get_current_user
from backend.models.agent_runtime import AgentTurnRequest, AgentTurnResponse
from backend.models.scoring import BestScheduleResponse
from backend.models.stored_schedule import (
    StoredScheduleResponse,
    StoredScheduleUpsertRequest,
)
from backend.models.user import User
from backend.models.user_planning import (
    AvailabilityWindowCreate,
    AvailabilityWindowResponse,
    AvailabilityWindowUpdate,
    PlanningContextResponse,
    StoredPlanningPreviewResponse,
    StoredPlanningRunRequest,
    UserBusyIntervalCreate,
    UserBusyIntervalResponse,
    UserBusyIntervalUpdate,
    UserTaskCreate,
    UserTaskResponse,
    UserTaskUpdate,
)
from backend.services.agent_runtime import AgentRuntimeService
from backend.services.user_planning import UserPlanningService

router = APIRouter()
service = UserPlanningService()
agent_runtime_service = AgentRuntimeService()


@router.get("/{user_id}/planning-context", response_model=PlanningContextResponse)
async def get_planning_context(
    user_id: str,
    current_user: User = Depends(get_current_user),
) -> PlanningContextResponse:
    ensure_user_access(user_id, current_user)
    return await service.get_planning_context(user_id)


@router.get("/{user_id}/tasks", response_model=list[UserTaskResponse])
async def list_tasks(
    user_id: str,
    statuses: list[str] | None = Query(default=None),
    current_user: User = Depends(get_current_user),
) -> list[UserTaskResponse]:
    ensure_user_access(user_id, current_user)
    return await service.list_tasks(user_id, statuses=statuses)


@router.post(
    "/{user_id}/tasks",
    response_model=UserTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    user_id: str,
    payload: UserTaskCreate,
    current_user: User = Depends(get_current_user),
) -> UserTaskResponse:
    ensure_user_access(user_id, current_user)
    return await service.create_task(user_id, payload)


@router.post(
    "/{user_id}/ai-task-drafts",
    response_model=AgentTurnResponse,
)
async def submit_ai_task_draft(
    user_id: str,
    payload: AgentTurnRequest,
    current_user: User = Depends(get_current_user),
) -> AgentTurnResponse:
    ensure_user_access(user_id, current_user)
    return await agent_runtime_service.handle_user_message(
        user_id,
        payload.text,
        conversation_id=payload.conversation_id,
    )


@router.get("/{user_id}/tasks/{task_id}", response_model=UserTaskResponse)
async def get_task(
    user_id: str,
    task_id: str,
    current_user: User = Depends(get_current_user),
) -> UserTaskResponse:
    ensure_user_access(user_id, current_user)
    return await service.get_task(user_id, task_id)


@router.patch("/{user_id}/tasks/{task_id}", response_model=UserTaskResponse)
async def update_task(
    user_id: str,
    task_id: str,
    payload: UserTaskUpdate,
    current_user: User = Depends(get_current_user),
) -> UserTaskResponse:
    ensure_user_access(user_id, current_user)
    return await service.update_task(user_id, task_id, payload)


@router.delete("/{user_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    user_id: str,
    task_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    ensure_user_access(user_id, current_user)
    await service.delete_task(user_id, task_id)


@router.get(
    "/{user_id}/availability-windows",
    response_model=list[AvailabilityWindowResponse],
)
async def list_availability_windows(
    user_id: str,
    current_user: User = Depends(get_current_user),
) -> list[AvailabilityWindowResponse]:
    ensure_user_access(user_id, current_user)
    return await service.list_availability_windows(user_id)


@router.post(
    "/{user_id}/availability-windows",
    response_model=AvailabilityWindowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_availability_window(
    user_id: str,
    payload: AvailabilityWindowCreate,
    current_user: User = Depends(get_current_user),
) -> AvailabilityWindowResponse:
    ensure_user_access(user_id, current_user)
    return await service.create_availability_window(user_id, payload)


@router.patch(
    "/{user_id}/availability-windows/{window_id}",
    response_model=AvailabilityWindowResponse,
)
async def update_availability_window(
    user_id: str,
    window_id: str,
    payload: AvailabilityWindowUpdate,
    current_user: User = Depends(get_current_user),
) -> AvailabilityWindowResponse:
    ensure_user_access(user_id, current_user)
    return await service.update_availability_window(user_id, window_id, payload)


@router.delete(
    "/{user_id}/availability-windows/{window_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_availability_window(
    user_id: str,
    window_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    ensure_user_access(user_id, current_user)
    await service.delete_availability_window(user_id, window_id)


@router.get("/{user_id}/busy-intervals", response_model=list[UserBusyIntervalResponse])
async def list_busy_intervals(
    user_id: str,
    current_user: User = Depends(get_current_user),
) -> list[UserBusyIntervalResponse]:
    ensure_user_access(user_id, current_user)
    return await service.list_busy_intervals(user_id)


@router.post(
    "/{user_id}/busy-intervals",
    response_model=UserBusyIntervalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_busy_interval(
    user_id: str,
    payload: UserBusyIntervalCreate,
    current_user: User = Depends(get_current_user),
) -> UserBusyIntervalResponse:
    ensure_user_access(user_id, current_user)
    return await service.create_busy_interval(user_id, payload)


@router.patch(
    "/{user_id}/busy-intervals/{interval_id}",
    response_model=UserBusyIntervalResponse,
)
async def update_busy_interval(
    user_id: str,
    interval_id: str,
    payload: UserBusyIntervalUpdate,
    current_user: User = Depends(get_current_user),
) -> UserBusyIntervalResponse:
    ensure_user_access(user_id, current_user)
    return await service.update_busy_interval(user_id, interval_id, payload)


@router.delete(
    "/{user_id}/busy-intervals/{interval_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_busy_interval(
    user_id: str,
    interval_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    ensure_user_access(user_id, current_user)
    await service.delete_busy_interval(user_id, interval_id)


@router.post(
    "/{user_id}/schedule-preview-from-stored-data",
    response_model=StoredPlanningPreviewResponse,
)
async def preview_schedule_from_stored_data(
    user_id: str,
    payload: StoredPlanningRunRequest,
    current_user: User = Depends(get_current_user),
) -> StoredPlanningPreviewResponse:
    ensure_user_access(user_id, current_user)
    return await service.preview_schedule_from_stored_data(user_id, payload)


@router.post(
    "/{user_id}/schedule-from-stored-data",
    response_model=StoredPlanningPreviewResponse,
)
async def generate_schedule_from_stored_data(
    user_id: str,
    payload: StoredPlanningRunRequest,
    current_user: User = Depends(get_current_user),
) -> StoredPlanningPreviewResponse:
    ensure_user_access(user_id, current_user)
    return await service.generate_schedule_from_stored_data(user_id, payload)


@router.post(
    "/{user_id}/best-schedule-from-stored-data",
    response_model=BestScheduleResponse,
)
async def generate_best_schedule_from_stored_data(
    user_id: str,
    payload: StoredPlanningRunRequest,
    current_user: User = Depends(get_current_user),
) -> BestScheduleResponse:
    ensure_user_access(user_id, current_user)
    return await service.generate_best_schedule_from_stored_data(user_id, payload)


@router.get(
    "/{user_id}/schedules/current",
    response_model=StoredScheduleResponse,
)
async def get_current_schedule(
    user_id: str,
    current_user: User = Depends(get_current_user),
) -> StoredScheduleResponse:
    ensure_user_access(user_id, current_user)
    return await service.get_current_schedule(user_id)


@router.post(
    "/{user_id}/schedules",
    response_model=StoredScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_schedule(
    user_id: str,
    payload: StoredScheduleUpsertRequest,
    current_user: User = Depends(get_current_user),
) -> StoredScheduleResponse:
    ensure_user_access(user_id, current_user)
    return await service.create_manual_schedule(user_id, payload)


@router.put(
    "/{user_id}/schedules/current",
    response_model=StoredScheduleResponse,
)
async def replace_current_schedule(
    user_id: str,
    payload: StoredScheduleUpsertRequest,
    current_user: User = Depends(get_current_user),
) -> StoredScheduleResponse:
    ensure_user_access(user_id, current_user)
    return await service.replace_current_schedule(user_id, payload)
