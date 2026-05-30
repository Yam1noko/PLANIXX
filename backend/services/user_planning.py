from datetime import datetime, timezone
import logging
from time import perf_counter

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from backend.core.observability import get_request_id
from backend.domain.scheduling.availability_recurrence import expand_availability_window
from backend.domain.scheduling.time_slots import interval_inside_any_window
from backend.models.scoring import BestScheduleResponse
from backend.models.scheduling import BusyInterval, PlanningRequest, TaskInput, TaskPlacementHint
from backend.models.stored_schedule import (
    StoredScheduledTaskResponse,
    StoredScheduleResponse,
    StoredScheduleUpsertRequest,
)
from backend.models.user_planning import (
    AvailabilityWindowCreate,
    AvailabilityWindowResponse,
    AvailabilityWindowUpdate,
    PlanningContextResponse,
    StoredPlanningPreviewResponse,
    StoredPlanningRunRequest,
    TimeWindow,
    UserBusyIntervalCreate,
    UserBusyIntervalResponse,
    UserBusyIntervalUpdate,
    UserTaskCreate,
    UserTaskResponse,
    UserTaskUpdate,
)
from backend.repositories.user_planning import UserPlanningRepository
from backend.repositories.planning import PlanningRepository
from backend.services.personalization import UserPreferenceService
from backend.services.scorer import ScorerChunkingService
from backend.services.scheduler import SchedulerService

logger = logging.getLogger(__name__)


class UserPlanningService:
    def __init__(self) -> None:
        self.repository = UserPlanningRepository()
        self.planning_repository = PlanningRepository()
        self.preference_service = UserPreferenceService()
        self.scorer_service = ScorerChunkingService()

    async def get_planning_context(self, user_id: str) -> PlanningContextResponse:
        profile = await self.preference_service.get_profile(user_id)
        tasks = await self.repository.list_tasks(user_id)
        availability_windows = await self.repository.list_availability_windows(user_id)
        busy_intervals = await self.repository.list_busy_intervals(user_id)

        return PlanningContextResponse(
            user_id=user_id,
            profile=profile,
            tasks=tasks,
            availability_windows=availability_windows,
            busy_intervals=busy_intervals,
        )

    async def list_tasks(
        self,
        user_id: str,
        *,
        statuses: list[str] | None = None,
    ) -> list[UserTaskResponse]:
        return await self.repository.list_tasks(user_id, statuses=statuses)

    async def get_task(self, user_id: str, task_id: str) -> UserTaskResponse:
        task = await self.repository.get_task(user_id, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        return task

    async def create_task(self, user_id: str, payload: UserTaskCreate) -> UserTaskResponse:
        try:
            return await self.repository.create_task(user_id, payload)
        except IntegrityError as exc:
            if self.repository.is_unique_violation(exc):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Task with this id already exists.",
                ) from exc
            raise

    async def update_task(
        self,
        user_id: str,
        task_id: str,
        payload: UserTaskUpdate,
    ) -> UserTaskResponse:
        current_task = await self.repository.get_task(user_id, task_id)
        if current_task is None:
            raise HTTPException(status_code=404, detail="Task not found.")

        merged_payload = {
            **current_task.model_dump(
                exclude={
                    "id",
                    "user_id",
                    "created_at",
                    "updated_at",
                },
                mode="python",
            ),
            **payload.model_dump(exclude_unset=True, mode="python"),
        }
        UserTaskCreate.model_validate(merged_payload)

        task = await self.repository.update_task(user_id, task_id, payload)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        return task

    async def delete_task(self, user_id: str, task_id: str) -> None:
        deleted = await self.repository.delete_task(user_id, task_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Task not found.")

    async def list_availability_windows(
        self,
        user_id: str,
    ) -> list[AvailabilityWindowResponse]:
        return await self.repository.list_availability_windows(user_id)

    async def create_availability_window(
        self,
        user_id: str,
        payload: AvailabilityWindowCreate,
    ) -> AvailabilityWindowResponse:
        try:
            normalized_payload = AvailabilityWindowCreate.model_validate(
                payload.model_dump(mode="python")
            )
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return await self.repository.create_availability_window(user_id, normalized_payload)

    async def update_availability_window(
        self,
        user_id: str,
        window_id: str,
        payload: AvailabilityWindowUpdate,
    ) -> AvailabilityWindowResponse:
        current_window = await self.repository.get_availability_window(user_id, window_id)
        if current_window is None:
            raise HTTPException(status_code=404, detail="Availability window not found.")

        patch = payload.model_dump(exclude_unset=True, mode="python")
        merged_payload = {
            **current_window.model_dump(
                exclude={
                    "id",
                    "user_id",
                    "created_at",
                    "updated_at",
                },
                mode="python",
            ),
            **patch,
        }
        if patch.get("is_recurring") is False and "recurrence_rule" not in patch:
            merged_payload["recurrence_rule"] = None
        if "recurrence_rule" in patch and patch["recurrence_rule"] is None:
            merged_payload["is_recurring"] = False

        try:
            normalized_payload = AvailabilityWindowCreate.model_validate(merged_payload)
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        window = await self.repository.update_availability_window(
            user_id,
            window_id,
            AvailabilityWindowUpdate.model_validate(
                normalized_payload.model_dump(mode="python")
            ),
        )
        if window is None:
            raise HTTPException(status_code=404, detail="Availability window not found.")
        return window

    async def delete_availability_window(self, user_id: str, window_id: str) -> None:
        deleted = await self.repository.delete_availability_window(user_id, window_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Availability window not found.")

    async def list_busy_intervals(self, user_id: str) -> list[UserBusyIntervalResponse]:
        return await self.repository.list_busy_intervals(user_id)

    async def create_busy_interval(
        self,
        user_id: str,
        payload: UserBusyIntervalCreate,
    ) -> UserBusyIntervalResponse:
        return await self.repository.create_busy_interval(user_id, payload)

    async def update_busy_interval(
        self,
        user_id: str,
        interval_id: str,
        payload: UserBusyIntervalUpdate,
    ) -> UserBusyIntervalResponse:
        interval = await self.repository.update_busy_interval(
            user_id,
            interval_id,
            payload,
        )
        if interval is None:
            raise HTTPException(status_code=404, detail="Busy interval not found.")
        return interval

    async def delete_busy_interval(self, user_id: str, interval_id: str) -> None:
        deleted = await self.repository.delete_busy_interval(user_id, interval_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Busy interval not found.")

    async def preview_schedule_from_stored_data(
        self,
        user_id: str,
        payload: StoredPlanningRunRequest,
    ) -> StoredPlanningPreviewResponse:
        started_at = perf_counter()
        logger.info(
            "Schedule preview requested | request_id=%s user_id=%s planning_start=%s planning_end=%s slot_minutes=%s task_statuses=%s",
            get_request_id(),
            user_id,
            payload.planning_start,
            payload.planning_end,
            payload.slot_minutes,
            payload.task_statuses,
        )
        request = await self._build_planning_request(user_id, payload)
        result = await SchedulerService.generate(request, persist_result=False)
        logger.info(
            "Schedule preview finished | request_id=%s user_id=%s status=%s scheduled=%s unscheduled=%s duration_ms=%s",
            get_request_id(),
            user_id,
            result.status,
            len(result.scheduled_tasks),
            len(result.unscheduled_tasks),
            round((perf_counter() - started_at) * 1000, 2),
        )
        return StoredPlanningPreviewResponse(
            planning_request=request.model_dump(mode="json"),
            planning_result=result,
        )

    async def generate_schedule_from_stored_data(
        self,
        user_id: str,
        payload: StoredPlanningRunRequest,
    ) -> StoredPlanningPreviewResponse:
        started_at = perf_counter()
        logger.info(
            "Schedule persist requested | request_id=%s user_id=%s planning_start=%s planning_end=%s slot_minutes=%s task_statuses=%s",
            get_request_id(),
            user_id,
            payload.planning_start,
            payload.planning_end,
            payload.slot_minutes,
            payload.task_statuses,
        )
        request = await self._build_planning_request(user_id, payload)
        result = await SchedulerService.generate(request, persist_result=True)
        logger.info(
            "Schedule persist finished | request_id=%s user_id=%s status=%s scheduled=%s unscheduled=%s duration_ms=%s",
            get_request_id(),
            user_id,
            result.status,
            len(result.scheduled_tasks),
            len(result.unscheduled_tasks),
            round((perf_counter() - started_at) * 1000, 2),
        )
        return StoredPlanningPreviewResponse(
            planning_request=request.model_dump(mode="json"),
            planning_result=result,
        )

    async def generate_best_schedule_from_stored_data(
        self,
        user_id: str,
        payload: StoredPlanningRunRequest,
    ) -> BestScheduleResponse:
        started_at = perf_counter()
        logger.info(
            "Best schedule requested | request_id=%s user_id=%s planning_start=%s planning_end=%s slot_minutes=%s task_statuses=%s",
            get_request_id(),
            user_id,
            payload.planning_start,
            payload.planning_end,
            payload.slot_minutes,
            payload.task_statuses,
        )
        request = await self._build_planning_request(user_id, payload)
        result = await self.scorer_service.generate_best_schedule(request)
        logger.info(
            "Best schedule finished | request_id=%s user_id=%s variant_id=%s scheduled=%s unscheduled=%s duration_ms=%s",
            get_request_id(),
            user_id,
            result.variant_id,
            len(result.scheduled_tasks),
            len(result.unscheduled_tasks),
            round((perf_counter() - started_at) * 1000, 2),
        )
        return result

    async def get_current_schedule(self, user_id: str) -> StoredScheduleResponse:
        schedule = await self.planning_repository.get_current_schedule(user_id)
        if schedule is None:
            raise HTTPException(status_code=404, detail="Current schedule not found.")
        return schedule

    async def create_manual_schedule(
        self,
        user_id: str,
        payload: StoredScheduleUpsertRequest,
    ) -> StoredScheduleResponse:
        try:
            return await self.planning_repository.create_manual_schedule(user_id, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def replace_current_schedule(
        self,
        user_id: str,
        payload: StoredScheduleUpsertRequest,
    ) -> StoredScheduleResponse:
        return await self.create_manual_schedule(user_id, payload)

    async def _build_planning_request(
        self,
        user_id: str,
        payload: StoredPlanningRunRequest,
    ) -> PlanningRequest:
        started_at = perf_counter()
        logger.info(
            "Planning request build started | request_id=%s user_id=%s use_warm_start=%s replan_from_current_schedule=%s",
            get_request_id(),
            user_id,
            payload.settings.use_warm_start,
            payload.settings.replan_from_current_schedule,
        )
        tasks = await self.repository.list_tasks(user_id, statuses=payload.task_statuses)
        availability_windows = await self.repository.list_availability_windows(user_id)
        busy_intervals = await self.repository.list_busy_intervals(user_id)
        reference_tzinfo = payload.planning_start.tzinfo

        try:
            expanded_availability_windows = self._expand_availability_windows(
                availability_windows=availability_windows,
                planning_start=payload.planning_start,
                planning_end=payload.planning_end,
                reference_tzinfo=reference_tzinfo,
            )
            normalized_busy_intervals = [
                self._to_busy_interval(interval, reference_tzinfo)
                for interval in busy_intervals
            ]
            task_inputs = [
                self._to_task_input(task, reference_tzinfo)
                for task in tasks
            ]
            placement_hints: list[TaskPlacementHint] = []
            if (
                user_id
                and (
                    payload.settings.use_warm_start
                    or payload.settings.replan_from_current_schedule
                )
            ):
                current_schedule = await self.planning_repository.get_current_schedule(user_id)
                if current_schedule is not None:
                    placement_hints = self._build_current_schedule_hints(
                        current_schedule=current_schedule,
                        planning_start=payload.planning_start,
                        planning_end=payload.planning_end,
                        reference_tzinfo=reference_tzinfo,
                    )
                    if payload.settings.replan_from_current_schedule:
                        task_inputs = self._lock_tasks_from_current_schedule(
                            tasks=task_inputs,
                            current_schedule=current_schedule,
                            planning_start=payload.planning_start,
                            planning_end=payload.planning_end,
                            available_windows=expanded_availability_windows,
                            busy_intervals=normalized_busy_intervals,
                            reference_tzinfo=reference_tzinfo,
                        )

            planning_request = PlanningRequest(
                user_id=user_id,
                planning_start=payload.planning_start,
                planning_end=payload.planning_end,
                slot_minutes=payload.slot_minutes,
                tasks=task_inputs,
                available_windows=expanded_availability_windows,
                busy_intervals=normalized_busy_intervals,
                placement_hints=placement_hints,
                settings=payload.settings,
            )
            logger.info(
                "Planning request build finished | request_id=%s user_id=%s tasks=%s availability_windows=%s busy_intervals=%s placement_hints=%s duration_ms=%s",
                get_request_id(),
                user_id,
                len(task_inputs),
                len(expanded_availability_windows),
                len(normalized_busy_intervals),
                len(placement_hints),
                round((perf_counter() - started_at) * 1000, 2),
            )
            return planning_request
        except (ValidationError, ValueError) as exc:
            if isinstance(exc, ValidationError):
                messages = [error["msg"] for error in exc.errors(include_url=False)]
                detail = messages[0] if len(messages) == 1 else messages
            else:
                detail = str(exc)
            logger.warning(
                "Planning request build failed | request_id=%s user_id=%s detail=%s duration_ms=%s",
                get_request_id(),
                user_id,
                detail,
                round((perf_counter() - started_at) * 1000, 2),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail,
            ) from exc

    def _expand_availability_windows(
        self,
        *,
        availability_windows: list[AvailabilityWindowResponse],
        planning_start: datetime,
        planning_end: datetime,
        reference_tzinfo,
    ) -> list[TimeWindow]:
        expanded: list[TimeWindow] = []
        for item in availability_windows:
            expanded.extend(
                expand_availability_window(
                    start=self._normalize_datetime(item.start, reference_tzinfo),
                    end=self._normalize_datetime(item.end, reference_tzinfo),
                    planning_start=planning_start,
                    planning_end=planning_end,
                    is_recurring=item.is_recurring,
                    recurrence_rule=item.recurrence_rule,
                )
            )

        expanded.sort(key=lambda window: (window.start, window.end))
        return self._merge_time_windows(expanded)

    def _merge_time_windows(self, windows: list[TimeWindow]) -> list[TimeWindow]:
        if not windows:
            return []

        merged: list[TimeWindow] = [windows[0]]
        for window in windows[1:]:
            current = merged[-1]
            if window.start <= current.end:
                if window.end > current.end:
                    current.end = window.end
                continue

            merged.append(window)

        return merged

    def _build_current_schedule_hints(
        self,
        *,
        current_schedule: StoredScheduleResponse,
        planning_start: datetime,
        planning_end: datetime,
        reference_tzinfo,
    ) -> list[TaskPlacementHint]:
        hints: list[TaskPlacementHint] = []
        for item in current_schedule.scheduled_tasks:
            start = self._normalize_datetime(item.start_at, reference_tzinfo)
            end = self._normalize_datetime(item.end_at, reference_tzinfo)
            if start < planning_start or end > planning_end:
                continue

            hints.append(
                TaskPlacementHint(
                    task_id=item.task_id,
                    start=start,
                    split_part_index=item.split_part_index,
                    split_part_count=item.split_part_count,
                )
            )

        return hints

    def _lock_tasks_from_current_schedule(
        self,
        *,
        tasks: list[TaskInput],
        current_schedule: StoredScheduleResponse,
        planning_start: datetime,
        planning_end: datetime,
        available_windows: list[TimeWindow],
        busy_intervals: list[BusyInterval],
        reference_tzinfo,
    ) -> list[TaskInput]:
        scheduled_by_task_id: dict[str, list[StoredScheduledTaskResponse]] = {}
        for item in current_schedule.scheduled_tasks:
            scheduled_by_task_id.setdefault(item.task_id, []).append(item)

        locked_tasks: list[TaskInput] = []
        for task in tasks:
            candidates = scheduled_by_task_id.get(task.id, [])
            if len(candidates) != 1:
                locked_tasks.append(task)
                continue

            scheduled_item = candidates[0]
            scheduled_start = self._normalize_datetime(scheduled_item.start_at, reference_tzinfo)
            scheduled_end = self._normalize_datetime(scheduled_item.end_at, reference_tzinfo)
            if not self._can_lock_current_placement(
                task=task,
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                planning_start=planning_start,
                planning_end=planning_end,
                available_windows=available_windows,
                busy_intervals=busy_intervals,
            ):
                locked_tasks.append(task)
                continue

            locked_tasks.append(
                task.model_copy(
                    update={
                        "is_fixed": True,
                        "fixed_start": scheduled_start,
                        "allow_splitting": False,
                        "min_split_part_minutes": None,
                    }
                )
            )

        return locked_tasks

    def _can_lock_current_placement(
        self,
        *,
        task: TaskInput,
        scheduled_start: datetime,
        scheduled_end: datetime,
        planning_start: datetime,
        planning_end: datetime,
        available_windows: list[TimeWindow],
        busy_intervals: list[BusyInterval],
    ) -> bool:
        if scheduled_start < planning_start or scheduled_end > planning_end:
            return False

        if int((scheduled_end - scheduled_start).total_seconds() // 60) != task.duration_minutes:
            return False

        if task.fixed_start is not None and task.fixed_start != scheduled_start:
            return False

        if task.earliest_start is not None and scheduled_start < task.earliest_start:
            return False

        hard_latest_end = task.latest_end or task.deadline
        if hard_latest_end is not None and scheduled_end > hard_latest_end:
            return False

        if (
            not task.is_fixed
            and available_windows
            and not interval_inside_any_window(
                scheduled_start,
                scheduled_end,
                available_windows,
            )
        ):
            return False

        if task.allowed_windows and not interval_inside_any_window(
            scheduled_start,
            scheduled_end,
            task.allowed_windows,
        ):
            return False

        return not any(
            scheduled_start < interval.end and scheduled_end > interval.start
            for interval in busy_intervals
        )

    def _to_task_input(
        self,
        task: UserTaskResponse,
        reference_tzinfo,
    ) -> TaskInput:
        return TaskInput(
            id=task.id,
            title=task.title,
            duration_minutes=task.duration_minutes,
            priority=task.priority,
            deadline=self._normalize_datetime(task.deadline, reference_tzinfo),
            earliest_start=self._normalize_datetime(task.earliest_start, reference_tzinfo),
            latest_end=self._normalize_datetime(task.latest_end, reference_tzinfo),
            preferred_windows=[
                TimeWindow(
                    start=self._normalize_datetime(window.start, reference_tzinfo),
                    end=self._normalize_datetime(window.end, reference_tzinfo),
                )
                for window in task.preferred_windows
            ],
            allowed_windows=[
                TimeWindow(
                    start=self._normalize_datetime(window.start, reference_tzinfo),
                    end=self._normalize_datetime(window.end, reference_tzinfo),
                )
                for window in task.allowed_windows
            ],
            is_fixed=task.is_fixed,
            fixed_start=self._normalize_datetime(task.fixed_start, reference_tzinfo),
            is_mandatory=task.is_mandatory,
            allow_splitting=task.allow_splitting,
            min_split_part_minutes=task.min_split_part_minutes,
            category=task.category,
            energy_required=task.energy_required,
        )

    def _to_busy_interval(
        self,
        interval: UserBusyIntervalResponse,
        reference_tzinfo,
    ) -> BusyInterval:
        return BusyInterval(
            title=interval.title,
            start=self._normalize_datetime(interval.start, reference_tzinfo),
            end=self._normalize_datetime(interval.end, reference_tzinfo),
        )

    def _normalize_datetime(
        self,
        value: datetime | None,
        reference_tzinfo,
    ) -> datetime | None:
        if value is None:
            return None

        if reference_tzinfo is None:
            if value.tzinfo is None:
                return value
            return value.astimezone(timezone.utc).replace(tzinfo=None)

        if value.tzinfo is None:
            return value.replace(tzinfo=reference_tzinfo)

        return value.astimezone(reference_tzinfo)
