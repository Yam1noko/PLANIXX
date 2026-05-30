from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.dependencies.auth import get_current_user, get_optional_current_user
from backend.models.scheduling import PlanningRequest, PlanningResult
from backend.models.user import User
from backend.services.scheduler import SchedulerService

router = APIRouter()


@router.post("/generate-preview", response_model=PlanningResult)
async def generate_schedule_preview(
    request: PlanningRequest,
    current_user: User | None = Depends(get_optional_current_user),
) -> PlanningResult:
    request = _bind_request_user(request, current_user, require_authenticated_user=False)
    return await SchedulerService.generate(request, persist_result=False)


@router.post("/generate", response_model=PlanningResult)
async def generate_schedule(
    request: PlanningRequest,
    current_user: User = Depends(get_current_user),
) -> PlanningResult:
    request = _bind_request_user(request, current_user, require_authenticated_user=True)
    return await SchedulerService.generate(request)


def _bind_request_user(
    request: PlanningRequest,
    current_user: User | None,
    *,
    require_authenticated_user: bool,
) -> PlanningRequest:
    if current_user is None:
        if require_authenticated_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication is required for this operation.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if request.user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated access is required when user_id is provided.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return request

    if request.user_id and request.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot use another user's identifier.",
        )

    return request.model_copy(update={"user_id": current_user.id})
