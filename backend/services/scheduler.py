import logging
from time import perf_counter

from backend.core.observability import get_request_id
from backend.domain.personalization.solver_preferences import build_solver_preferences
from backend.domain.scheduling.solver import OrToolsSchedulerSolver
from backend.models.personalization import UserPreferenceProfile
from backend.models.scheduling import (
    PlanningRequest,
    PlanningResult,
    ProfileContext,
    ScheduleVariant,
    UnscheduledTask,
    Violation,
)
from backend.repositories.planning import PlanningRepository
from backend.services.personalization import UserPreferenceService

logger = logging.getLogger(__name__)


class SchedulerService:
    @staticmethod
    async def generate(
        request: PlanningRequest,
        persist_result: bool = True,
    ) -> PlanningResult:
        started_at = perf_counter()
        logger.info(
            "Scheduler generate started | request_id=%s user_id=%s persist_result=%s tasks=%s slot_minutes=%s planning_start=%s planning_end=%s",
            get_request_id(),
            request.user_id,
            persist_result,
            len(request.tasks),
            request.slot_minutes,
            request.planning_start,
            request.planning_end,
        )
        validation_error = SchedulerService._validate_business_rules(request)
        profile_context = ProfileContext(user_id=request.user_id, profile_used=False)

        if validation_error is not None:
            unscheduled_tasks = [
                UnscheduledTask(
                    task_id=task.id,
                    title=task.title,
                    task=task,
                    reason="VALIDATION_FAILED",
                )
                for task in request.tasks
            ]
            result = PlanningResult(
                status="partial",
                scheduled_tasks=[],
                unscheduled_tasks=unscheduled_tasks,
                schedule_variants=[
                    ScheduleVariant(
                        variant_id=1,
                        scheduled_tasks=[],
                        unscheduled_tasks=unscheduled_tasks,
                        metadata={
                            "solver_status": "VALIDATION_FAILED",
                            "strategy": "validation_fallback",
                            "total_scheduled_minutes": 0,
                            "total_unscheduled_minutes": sum(
                                task.duration_minutes
                                for task in request.tasks
                            ),
                        },
                    )
                ],
                violations=[validation_error],
                profile_context=profile_context,
                metadata={
                    "solver_status": "VALIDATION_FAILED",
                    "variant_count": 1,
                    "total_scheduled_minutes": 0,
                    "total_unscheduled_minutes": sum(
                        task.duration_minutes
                        for task in request.tasks
                    ),
                },
            )
            logger.warning(
                "Scheduler generate validation fallback | request_id=%s user_id=%s code=%s duration_ms=%s",
                get_request_id(),
                request.user_id,
                validation_error.code,
                round((perf_counter() - started_at) * 1000, 2),
            )
            return result

        user_preferences = None
        user_profile: UserPreferenceProfile | None = None
        if request.user_id:
            profile_started_at = perf_counter()
            preference_service = UserPreferenceService()
            user_profile = await preference_service.get_profile(request.user_id)
            user_preferences = build_solver_preferences(user_profile)
            profile_context = ProfileContext(
                user_id=request.user_id,
                profile_used=True,
                profile=user_profile,
            )
            logger.info(
                "Scheduler profile loaded | request_id=%s user_id=%s duration_ms=%s",
                get_request_id(),
                request.user_id,
                round((perf_counter() - profile_started_at) * 1000, 2),
            )

        solver = OrToolsSchedulerSolver()
        solve_started_at = perf_counter()
        logger.info(
            "Scheduler solve started | request_id=%s user_id=%s",
            get_request_id(),
            request.user_id,
        )
        result = solver.solve(
            request=request,
            user_preferences=user_preferences,
        )
        logger.info(
            "Scheduler solve finished | request_id=%s user_id=%s status=%s variants=%s scheduled=%s unscheduled=%s solver_status=%s duration_ms=%s",
            get_request_id(),
            request.user_id,
            result.status,
            len(result.schedule_variants),
            len(result.scheduled_tasks),
            len(result.unscheduled_tasks),
            result.metadata.get("solver_status"),
            round((perf_counter() - solve_started_at) * 1000, 2),
        )
        result.source_request = request
        result.profile_context = profile_context

        if request.user_id and persist_result:
            persist_started_at = perf_counter()
            logger.info(
                "Scheduler persist started | request_id=%s user_id=%s",
                get_request_id(),
                request.user_id,
            )
            planning_repository = PlanningRepository()
            await planning_repository.save_result(request, result)
            logger.info(
                "Scheduler persist finished | request_id=%s user_id=%s duration_ms=%s",
                get_request_id(),
                request.user_id,
                round((perf_counter() - persist_started_at) * 1000, 2),
            )

        logger.info(
            "Scheduler generate finished | request_id=%s user_id=%s total_duration_ms=%s",
            get_request_id(),
            request.user_id,
            round((perf_counter() - started_at) * 1000, 2),
        )

        return result

    @staticmethod
    def _validate_business_rules(request: PlanningRequest) -> Violation | None:
        if request.slot_minutes not in {5, 10, 15, 30, 60}:
            return Violation(
                code="INVALID_SLOT_SIZE",
                message="slot_minutes must be one of: 5, 10, 15, 30, 60.",
            )

        if request.planning_end <= request.planning_start:
            return Violation(
                code="INVALID_TIME_RANGE",
                message="planning_end must be later than planning_start.",
            )

        if request.settings.min_break_minutes != 0:
            return Violation(
                code="UNSUPPORTED_SETTING",
                message="min_break_minutes is not supported in MVP.",
            )

        return None
