from datetime import datetime
import logging
from time import perf_counter

from backend.core.observability import get_request_id
from backend.domain.scoring.variant_scorer import SolverVariantScorer
from backend.models.scoring import (
    BestScheduleResponse,
    BestVariantSelectionResponse,
    SolverResultChunk,
    SolverResultChunkingResponse,
)
from backend.models.scheduling import PlanningRequest, PlanningResult, ScheduleVariant
from backend.repositories.planning import PlanningRepository
from backend.repositories.scorer_chunks import ScorerChunkRepository
from backend.services.scheduler import SchedulerService

logger = logging.getLogger(__name__)


class ScorerChunkingService:
    def __init__(self):
        self.repository = ScorerChunkRepository()
        self.planning_repository = PlanningRepository()
        self.variant_scorer = SolverVariantScorer()

    def chunk_solver_result(self, result: PlanningResult) -> SolverResultChunkingResponse:
        started_at = perf_counter()
        logger.info(
            "Scorer chunking started | request_id=%s variants=%s scheduled=%s unscheduled=%s",
            get_request_id(),
            len(result.schedule_variants),
            len(result.scheduled_tasks),
            len(result.unscheduled_tasks),
        )
        response = self._build_chunking_response(result)
        saved_response = self.repository.save_chunking_response(response)
        logger.info(
            "Scorer chunking finished | request_id=%s batch_id=%s total_chunks=%s duration_ms=%s",
            get_request_id(),
            saved_response.batch_id,
            saved_response.total_chunks,
            round((perf_counter() - started_at) * 1000, 2),
        )
        return saved_response

    def _build_chunking_response(
        self,
        result: PlanningResult,
    ) -> SolverResultChunkingResponse:
        variants = result.schedule_variants or [
            ScheduleVariant(
                variant_id=1,
                scheduled_tasks=result.scheduled_tasks,
                unscheduled_tasks=result.unscheduled_tasks,
                metadata=result.metadata,
            )
        ]

        batch_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        chunk_id = 1
        chunks = [
            SolverResultChunk(
                chunk_id=chunk_id,
                planning_status=result.status,
                profile_context=result.profile_context,
                source_request=result.source_request,
                schedule_variant=variant,
                violations=result.violations,
                metadata={
                    **result.metadata,
                    "variant_id": variant.variant_id,
                },
            )
            for variant in variants
        ]

        response = SolverResultChunkingResponse(
            batch_id=batch_id,
            total_chunks=len(chunks),
            chunks=chunks,
        )
        return response

    def get_chunk(
        self,
        batch_id: str,
        chunk_id: int,
        variant_id: int | None = None,
    ) -> SolverResultChunk:
        return self.repository.get_chunk(batch_id, chunk_id, variant_id)

    def select_best_variant(
        self,
        response: SolverResultChunkingResponse,
    ) -> BestVariantSelectionResponse:
        return self.variant_scorer.select_best_variant(response)

    async def generate_best_schedule(
        self,
        request: PlanningRequest,
    ) -> BestScheduleResponse:
        started_at = perf_counter()
        logger.info(
            "Best schedule pipeline started | request_id=%s user_id=%s tasks=%s",
            get_request_id(),
            request.user_id,
            len(request.tasks),
        )
        planning_result = await SchedulerService.generate(
            request,
            persist_result=False,
        )
        logger.info(
            "Best schedule solver result ready | request_id=%s status=%s variants=%s scheduled=%s unscheduled=%s",
            get_request_id(),
            planning_result.status,
            len(planning_result.schedule_variants),
            len(planning_result.scheduled_tasks),
            len(planning_result.unscheduled_tasks),
        )
        chunked_result = self._build_chunking_response(planning_result)
        select_started_at = perf_counter()
        selected = self.select_best_variant(chunked_result)
        logger.info(
            "Best schedule selection finished | request_id=%s batch_id=%s best_variant_id=%s duration_ms=%s",
            get_request_id(),
            selected.batch_id,
            selected.best_variant_id,
            round((perf_counter() - select_started_at) * 1000, 2),
        )
        best_variant = selected.selected_chunk.schedule_variant

        selected_result = self._build_selected_result(
            planning_result=planning_result,
            selected=selected,
        )
        if request.user_id:
            persist_started_at = perf_counter()
            await self.planning_repository.save_result(request, selected_result)
            logger.info(
                "Best schedule persist finished | request_id=%s user_id=%s variant_id=%s duration_ms=%s",
                get_request_id(),
                request.user_id,
                best_variant.variant_id,
                round((perf_counter() - persist_started_at) * 1000, 2),
            )

        response = BestScheduleResponse(
            variant_id=best_variant.variant_id,
            scheduled_tasks=best_variant.scheduled_tasks,
            unscheduled_tasks=best_variant.unscheduled_tasks,
        )
        logger.info(
            "Best schedule pipeline finished | request_id=%s variant_id=%s scheduled=%s unscheduled=%s total_duration_ms=%s",
            get_request_id(),
            response.variant_id,
            len(response.scheduled_tasks),
            len(response.unscheduled_tasks),
            round((perf_counter() - started_at) * 1000, 2),
        )
        return response

    def _build_selected_result(
        self,
        *,
        planning_result: PlanningResult,
        selected: BestVariantSelectionResponse,
    ) -> PlanningResult:
        best_variant = selected.selected_chunk.schedule_variant
        return planning_result.model_copy(
            deep=True,
            update={
                "scheduled_tasks": best_variant.scheduled_tasks,
                "unscheduled_tasks": best_variant.unscheduled_tasks,
                "schedule_variants": [best_variant],
                "metadata": {
                    **planning_result.metadata,
                    "best_variant_id": best_variant.variant_id,
                    "scoring": [
                        breakdown.model_dump(mode="json")
                        for breakdown in selected.variant_scores
                    ],
                },
            },
        )
