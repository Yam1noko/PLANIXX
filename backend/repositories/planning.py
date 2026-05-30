from collections.abc import Iterable
import logging
from time import perf_counter

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.observability import get_request_id
from backend.db.database import AsyncSessionLocal
from backend.models.schedule import AvailabilityWindow, BusyInterval, Schedule, ScheduledTask
from backend.models.stored_schedule import (
    StoredScheduledTaskCreate,
    StoredScheduledTaskResponse,
    StoredScheduleResponse,
    StoredScheduleUpsertRequest,
)
from backend.models.task import Task
from backend.models.user import User
from backend.models.scheduling import PlanningRequest, PlanningResult, ScheduleVariant, TaskInput

logger = logging.getLogger(__name__)


class PlanningRepository:
    async def save_result(
        self,
        request: PlanningRequest,
        result: PlanningResult,
    ) -> None:
        if not request.user_id:
            return

        started_at = perf_counter()
        logger.info(
            "PlanningRepository.save_result started | request_id=%s user_id=%s variants=%s scheduled=%s unscheduled=%s",
            get_request_id(),
            request.user_id,
            len(result.schedule_variants),
            len(result.scheduled_tasks),
            len(result.unscheduled_tasks),
        )
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await self._ensure_user(session, request.user_id)
                await self._upsert_tasks(session, request.user_id, request.tasks)
                await self._clear_current_schedule(session, request.user_id)

                schedule = Schedule(
                    user_id=request.user_id,
                    planning_start=request.planning_start,
                    planning_end=request.planning_end,
                    slot_minutes=request.slot_minutes,
                    status=result.status,
                    is_current=True,
                    selected_variant_id=self._get_selected_variant_id(result),
                    source_request=request.model_dump(mode="json"),
                    profile_context=result.profile_context.model_dump(mode="json"),
                    schedule_metadata=result.metadata,
                )
                session.add(schedule)
                await session.flush()

                for window in request.available_windows:
                    session.add(
                        AvailabilityWindow(
                            user_id=request.user_id,
                            schedule_id=schedule.id,
                            title=None,
                            start_at=window.start,
                            end_at=window.end,
                            source="request",
                        )
                    )

                for interval in request.busy_intervals:
                    session.add(
                        BusyInterval(
                            user_id=request.user_id,
                            schedule_id=schedule.id,
                            title=interval.title,
                            start_at=interval.start,
                            end_at=interval.end,
                            source="request",
                        )
                    )

                variants = result.schedule_variants or [
                    ScheduleVariant(
                        variant_id=1,
                        scheduled_tasks=result.scheduled_tasks,
                        unscheduled_tasks=result.unscheduled_tasks,
                        metadata=result.metadata,
                    )
                ]

                for variant in variants:
                    for scheduled_task in variant.scheduled_tasks:
                        session.add(
                            ScheduledTask(
                                schedule_id=schedule.id,
                                task_id=scheduled_task.task_id,
                                variant_id=variant.variant_id,
                                title=scheduled_task.title,
                                start_at=scheduled_task.start,
                                end_at=scheduled_task.end,
                                duration_minutes=scheduled_task.duration_minutes,
                                priority=scheduled_task.priority,
                                is_mandatory=scheduled_task.is_mandatory,
                                split_part_index=scheduled_task.split_part_index,
                                split_part_count=scheduled_task.split_part_count,
                                payload=scheduled_task.task.model_dump(mode="json"),
                            )
                        )
        logger.info(
            "PlanningRepository.save_result finished | request_id=%s user_id=%s duration_ms=%s",
            get_request_id(),
            request.user_id,
            round((perf_counter() - started_at) * 1000, 2),
        )

    async def get_current_schedule(self, user_id: str) -> StoredScheduleResponse | None:
        async with AsyncSessionLocal() as session:
            statement = (
                select(Schedule)
                .where(
                    Schedule.user_id == user_id,
                    Schedule.is_current.is_(True),
                )
                .order_by(Schedule.created_at.desc())
            )
            schedule = await session.scalar(statement)
            if schedule is None:
                return None

            await session.refresh(schedule, attribute_names=["scheduled_tasks"])
            return self._to_stored_schedule_response(schedule)

    async def create_manual_schedule(
        self,
        user_id: str,
        payload: StoredScheduleUpsertRequest,
    ) -> StoredScheduleResponse:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await self._ensure_user(session, user_id)
                tasks_by_id = await self._get_user_tasks_by_id(
                    session,
                    user_id,
                    [item.task_id for item in payload.scheduled_tasks],
                )
                self._validate_manual_schedule_payload(payload, tasks_by_id)
                await self._clear_current_schedule(session, user_id)

                schedule = Schedule(
                    user_id=user_id,
                    planning_start=payload.planning_start,
                    planning_end=payload.planning_end,
                    slot_minutes=payload.slot_minutes,
                    status=payload.status,
                    is_current=True,
                    selected_variant_id=payload.selected_variant_id,
                    source_request=payload.source_request or {"source": "manual_frontend"},
                    profile_context=payload.profile_context,
                    schedule_metadata={
                        "source": "manual_frontend",
                        "manual": True,
                        **(payload.schedule_metadata or {}),
                    },
                )
                session.add(schedule)
                await session.flush()

                for item in payload.scheduled_tasks:
                    task = tasks_by_id[item.task_id]
                    duration_minutes = int(
                        (item.end_at - item.start_at).total_seconds() // 60
                    )
                    session.add(
                        ScheduledTask(
                            schedule_id=schedule.id,
                            task_id=task.id,
                            variant_id=item.variant_id,
                            title=task.title,
                            start_at=item.start_at,
                            end_at=item.end_at,
                            duration_minutes=duration_minutes,
                            priority=task.priority,
                            is_mandatory=task.is_mandatory,
                            split_part_index=item.split_part_index,
                            split_part_count=item.split_part_count,
                            payload={
                                "task_id": task.id,
                                "title": task.title,
                                "category": task.category,
                                "energy_required": task.energy_required,
                                "status": task.status,
                            },
                        )
                    )

                await session.flush()
                await session.refresh(schedule, attribute_names=["scheduled_tasks"])
                return self._to_stored_schedule_response(schedule)

    async def _ensure_user(self, session: AsyncSession, user_id: str) -> None:
        db_user = await session.get(User, user_id)
        if db_user is None:
            session.add(User(id=user_id))

    async def _clear_current_schedule(self, session: AsyncSession, user_id: str) -> None:
        await session.execute(
            update(Schedule)
            .where(
                Schedule.user_id == user_id,
                Schedule.is_current.is_(True),
            )
            .values(is_current=False)
        )

    async def _get_user_tasks_by_id(
        self,
        session: AsyncSession,
        user_id: str,
        task_ids: list[str],
    ) -> dict[str, Task]:
        if not task_ids:
            return {}

        statement = select(Task).where(
            Task.user_id == user_id,
            Task.id.in_(task_ids),
        )
        tasks = (await session.scalars(statement)).all()
        return {task.id: task for task in tasks}

    async def _upsert_tasks(
        self,
        session: AsyncSession,
        user_id: str,
        tasks: list[TaskInput],
    ) -> None:
        for task in tasks:
            db_task = await session.get(Task, task.id)
            task_data = {
                "user_id": user_id,
                "title": task.title,
                "description": None,
                "duration_minutes": task.duration_minutes,
                "priority": task.priority,
                "category": task.category,
                "energy_required": task.energy_required,
                "status": "active",
                "deadline": task.deadline,
                "earliest_start": task.earliest_start,
                "latest_end": task.latest_end,
                "fixed_start": task.fixed_start,
                "is_mandatory": task.is_mandatory,
                "is_fixed": task.is_fixed,
                "allow_splitting": task.allow_splitting,
                "min_split_part_minutes": task.min_split_part_minutes,
                "preferred_windows": [
                    window.model_dump(mode="json") for window in task.preferred_windows
                ],
                "allowed_windows": [
                    window.model_dump(mode="json") for window in task.allowed_windows
                ],
                "constraints": None,
                "llm_metadata": None,
            }

            if db_task is None:
                session.add(Task(id=task.id, **task_data))
                continue

            for field_name, field_value in task_data.items():
                setattr(db_task, field_name, field_value)

    def _get_selected_variant_id(self, result: PlanningResult) -> int | None:
        if result.schedule_variants and result.scheduled_tasks:
            selected_signature = self._build_task_signature(result.scheduled_tasks)
            for variant in result.schedule_variants:
                if self._build_task_signature(variant.scheduled_tasks) == selected_signature:
                    return variant.variant_id

        if result.schedule_variants:
            return result.schedule_variants[0].variant_id

        if result.scheduled_tasks:
            return 1

        return None

    def _validate_manual_schedule_payload(
        self,
        payload: StoredScheduleUpsertRequest,
        tasks_by_id: dict[str, Task],
    ) -> None:
        if payload.slot_minutes not in {5, 10, 15, 30, 60}:
            raise ValueError("slot_minutes must be one of: 5, 10, 15, 30, 60.")

        if not self._is_aligned(
            payload.planning_start,
            payload.planning_end,
            payload.slot_minutes,
        ):
            raise ValueError("planning_end must align with slot_minutes.")

        sorted_items = sorted(
            payload.scheduled_tasks,
            key=lambda item: (item.start_at, item.end_at, item.task_id),
        )
        seen_task_ids = set()

        for item in sorted_items:
            if item.task_id not in tasks_by_id:
                raise ValueError(
                    f"Task '{item.task_id}' does not exist or does not belong to the user."
                )

            if item.task_id in seen_task_ids and item.split_part_count is None:
                raise ValueError(
                    f"Task '{item.task_id}' is duplicated in schedule without split metadata."
                )
            seen_task_ids.add(item.task_id)

            if item.start_at < payload.planning_start or item.end_at > payload.planning_end:
                raise ValueError(
                    f"Scheduled task '{item.task_id}' must stay within planning range."
                )

            if not self._is_aligned(
                payload.planning_start,
                item.start_at,
                payload.slot_minutes,
            ):
                raise ValueError(
                    f"Scheduled task '{item.task_id}' start_at must align with slot_minutes."
                )

            if not self._is_aligned(
                payload.planning_start,
                item.end_at,
                payload.slot_minutes,
            ):
                raise ValueError(
                    f"Scheduled task '{item.task_id}' end_at must align with slot_minutes."
                )

            duration_minutes = int((item.end_at - item.start_at).total_seconds() // 60)
            if duration_minutes <= 0 or duration_minutes % payload.slot_minutes != 0:
                raise ValueError(
                    f"Scheduled task '{item.task_id}' duration must align with slot_minutes."
                )

        for previous, current in zip(sorted_items, sorted_items[1:]):
            if current.start_at < previous.end_at:
                raise ValueError(
                    f"Scheduled tasks '{previous.task_id}' and '{current.task_id}' overlap."
                )

    @staticmethod
    def _is_aligned(start, value, slot_minutes: int) -> bool:
        return (value - start).total_seconds() % (slot_minutes * 60) == 0

    def _to_stored_schedule_response(self, schedule: Schedule) -> StoredScheduleResponse:
        scheduled_tasks = self._get_selected_variant_tasks(schedule)
        scheduled_tasks.sort(key=lambda item: (item.start_at, item.end_at, item.created_at))

        return StoredScheduleResponse(
            id=schedule.id,
            user_id=schedule.user_id,
            planning_start=schedule.planning_start,
            planning_end=schedule.planning_end,
            slot_minutes=schedule.slot_minutes,
            status=schedule.status,
            is_current=schedule.is_current,
            selected_variant_id=schedule.selected_variant_id,
            source_request=schedule.source_request,
            profile_context=schedule.profile_context,
            schedule_metadata=schedule.schedule_metadata,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
            scheduled_tasks=[
                StoredScheduledTaskResponse(
                    id=item.id,
                    schedule_id=item.schedule_id,
                    task_id=item.task_id,
                    variant_id=item.variant_id,
                    title=item.title,
                    start_at=item.start_at,
                    end_at=item.end_at,
                    duration_minutes=item.duration_minutes,
                    priority=item.priority,
                    is_mandatory=item.is_mandatory,
                    split_part_index=item.split_part_index,
                    split_part_count=item.split_part_count,
                    payload=item.payload,
                    created_at=item.created_at,
                )
                for item in scheduled_tasks
            ],
        )

    def _get_selected_variant_tasks(self, schedule: Schedule) -> list[ScheduledTask]:
        if schedule.selected_variant_id is not None:
            selected_items = [
                item
                for item in schedule.scheduled_tasks
                if item.variant_id == schedule.selected_variant_id
            ]
            if selected_items:
                return selected_items

        scheduled_tasks = sorted(
            schedule.scheduled_tasks,
            key=lambda item: (
                item.variant_id if item.variant_id is not None else -1,
                item.start_at,
                item.end_at,
                item.created_at,
            ),
        )
        if not scheduled_tasks:
            return []

        first_variant_id = scheduled_tasks[0].variant_id
        return [
            item
            for item in scheduled_tasks
            if item.variant_id == first_variant_id
        ]

    @staticmethod
    def _build_task_signature(tasks: Iterable) -> list[tuple]:
        return sorted(
            (
                task.task_id,
                task.start if hasattr(task, "start") else task.start_at,
                task.end if hasattr(task, "end") else task.end_at,
                task.split_part_index,
                task.split_part_count,
            )
            for task in tasks
        )
