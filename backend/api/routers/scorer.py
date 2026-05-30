from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies.auth import get_current_user
from backend.models.scoring import (
    BestScheduleResponse,
    BestVariantSelectionResponse,
    SolverResultChunk,
    SolverResultChunkingResponse,
)
from backend.models.scheduling import PlanningRequest, PlanningResult
from backend.models.user import User
from backend.services.scorer import ScorerChunkingService

router = APIRouter()
service = ScorerChunkingService()


@router.post("/chunk-solver-output", response_model=SolverResultChunkingResponse)
def chunk_solver_output(result: PlanningResult) -> SolverResultChunkingResponse:
    return service.chunk_solver_result(result)


@router.post(
    "/generate-best-schedule",
    response_model=BestScheduleResponse,
)
async def generate_best_schedule(
    request: PlanningRequest,
    current_user: User = Depends(get_current_user),
) -> BestScheduleResponse:
    if request.user_id and request.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You cannot use another user's identifier.",
        )

    request = request.model_copy(update={"user_id": current_user.id})
    return await service.generate_best_schedule(request)


@router.post(
    "/select-best-variant",
    response_model=BestVariantSelectionResponse,
)
def select_best_variant(
    response: SolverResultChunkingResponse,
) -> BestVariantSelectionResponse:
    try:
        return service.select_best_variant(response)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/chunks/{batch_id}/{chunk_id}", response_model=SolverResultChunk)
def get_chunk(
    batch_id: str,
    chunk_id: int,
    variant_id: int | None = None,
) -> SolverResultChunk:
    try:
        return service.get_chunk(batch_id, chunk_id, variant_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chunk not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
