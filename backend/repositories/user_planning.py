from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.db.database import AsyncSessionLocal
from backend.models.schedule import AvailabilityWindow, BusyInterval
from backend.models.task import Task
from backend.models.user_planning import (
    AvailabilityWindowCreate,
    AvailabilityWindowResponse,
    AvailabilityWindowUpdate,
    TimeWindow,
    UserBusyIntervalCreate,
    UserBusyIntervalResponse,
    UserBusyIntervalUpdate,
    UserTaskCreate,
    UserTaskResponse,
    UserTaskUpdate,
)


class UserPlanningRepository:
    async def list_tasks(
        self,
        user_id: str,
        *,
        statuses: list[str] | None = None,
    ) -> list[UserTaskResponse]:
        async with AsyncSessionLocal() as session:
            statement = select(Task).where(Task.user_id == user_id)
            if statuses:
                statement = statement.where(Task.status.in_(statuses))
            statement = statement.order_by(Task.created_at.desc())
            tasks = (await session.scalars(statement)).all()
            return [self._to_task_response(task) for task in tasks]

    async def get_task(self, user_id: str, task_id: str) -> UserTaskResponse | None:
        async with AsyncSessionLocal() as session:
            statement = select(Task).where(
                Task.user_id == user_id,
                Task.id == task_id,
            )
            task = await session.scalar(statement)
            return self._to_task_response(task) if task else None

    async def create_task(self, user_id: str, payload: UserTaskCreate) -> UserTaskResponse:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                task = Task(
                    id=payload.id or str(uuid4()),
                    user_id=user_id,
                    title=payload.title,
                    description=payload.description,
                    duration_minutes=payload.duration_minutes,
                    priority=payload.priority,
                    category=payload.category,
                    energy_required=payload.energy_required,
                    status=payload.status,
                    deadline=payload.deadline,
                    earliest_start=payload.earliest_start,
                    latest_end=payload.latest_end,
                    fixed_start=payload.fixed_start,
                    is_mandatory=payload.is_mandatory,
                    is_fixed=payload.is_fixed,
                    allow_splitting=payload.allow_splitting,
                    min_split_part_minutes=payload.min_split_part_minutes,
                    preferred_windows=self._serialize_time_windows(
                        payload.preferred_windows
                    ),
                    allowed_windows=self._serialize_time_windows(
                        payload.allowed_windows
                    ),
                    constraints=payload.constraints,
                    llm_metadata=payload.llm_metadata,
                )
                session.add(task)
                await session.flush()
                await session.refresh(task)
                return self._to_task_response(task)

    async def update_task(
        self,
        user_id: str,
        task_id: str,
        payload: UserTaskUpdate,
    ) -> UserTaskResponse | None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                statement = select(Task).where(
                    Task.user_id == user_id,
                    Task.id == task_id,
                )
                task = await session.scalar(statement)
                if task is None:
                    return None

                patch = payload.model_dump(exclude_unset=True)
                for field_name, value in patch.items():
                    if field_name in {"preferred_windows", "allowed_windows"} and value is not None:
                        value = self._serialize_time_windows(value)
                    setattr(task, field_name, value)

                await session.flush()
                await session.refresh(task)
                return self._to_task_response(task)

    async def delete_task(self, user_id: str, task_id: str) -> bool:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                statement = select(Task).where(
                    Task.user_id == user_id,
                    Task.id == task_id,
                )
                task = await session.scalar(statement)
                if task is None:
                    return False

                await session.delete(task)
                return True

    async def list_availability_windows(
        self,
        user_id: str,
    ) -> list[AvailabilityWindowResponse]:
        async with AsyncSessionLocal() as session:
            statement = (
                select(AvailabilityWindow)
                .where(
                    AvailabilityWindow.user_id == user_id,
                    AvailabilityWindow.schedule_id.is_(None),
                )
                .order_by(AvailabilityWindow.start_at.asc())
            )
            windows = (await session.scalars(statement)).all()
            return [self._to_availability_response(window) for window in windows]

    async def get_availability_window(
        self,
        user_id: str,
        window_id: str,
    ) -> AvailabilityWindowResponse | None:
        async with AsyncSessionLocal() as session:
            statement = select(AvailabilityWindow).where(
                AvailabilityWindow.user_id == user_id,
                AvailabilityWindow.id == window_id,
                AvailabilityWindow.schedule_id.is_(None),
            )
            window = await session.scalar(statement)
            return self._to_availability_response(window) if window else None

    async def create_availability_window(
        self,
        user_id: str,
        payload: AvailabilityWindowCreate,
    ) -> AvailabilityWindowResponse:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                window = AvailabilityWindow(
                    user_id=user_id,
                    title=payload.title,
                    start_at=payload.start,
                    end_at=payload.end,
                    is_recurring=payload.is_recurring,
                    recurrence_rule=payload.recurrence_rule,
                    source=payload.source,
                )
                session.add(window)
                await session.flush()
                await session.refresh(window)
                return self._to_availability_response(window)

    async def update_availability_window(
        self,
        user_id: str,
        window_id: str,
        payload: AvailabilityWindowUpdate,
    ) -> AvailabilityWindowResponse | None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                statement = select(AvailabilityWindow).where(
                    AvailabilityWindow.user_id == user_id,
                    AvailabilityWindow.id == window_id,
                    AvailabilityWindow.schedule_id.is_(None),
                )
                window = await session.scalar(statement)
                if window is None:
                    return None

                patch = payload.model_dump(exclude_unset=True)
                if "start" in patch:
                    window.start_at = patch.pop("start")
                if "end" in patch:
                    window.end_at = patch.pop("end")
                for field_name, value in patch.items():
                    setattr(window, field_name, value)

                await session.flush()
                await session.refresh(window)
                return self._to_availability_response(window)

    async def delete_availability_window(self, user_id: str, window_id: str) -> bool:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                statement = select(AvailabilityWindow).where(
                    AvailabilityWindow.user_id == user_id,
                    AvailabilityWindow.id == window_id,
                    AvailabilityWindow.schedule_id.is_(None),
                )
                window = await session.scalar(statement)
                if window is None:
                    return False

                await session.delete(window)
                return True

    async def list_busy_intervals(
        self,
        user_id: str,
    ) -> list[UserBusyIntervalResponse]:
        async with AsyncSessionLocal() as session:
            statement = (
                select(BusyInterval)
                .where(
                    BusyInterval.user_id == user_id,
                    BusyInterval.schedule_id.is_(None),
                )
                .order_by(BusyInterval.start_at.asc())
            )
            intervals = (await session.scalars(statement)).all()
            return [self._to_busy_interval_response(interval) for interval in intervals]

    async def create_busy_interval(
        self,
        user_id: str,
        payload: UserBusyIntervalCreate,
    ) -> UserBusyIntervalResponse:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                interval = BusyInterval(
                    user_id=user_id,
                    title=payload.title,
                    start_at=payload.start,
                    end_at=payload.end,
                    source=payload.source,
                    external_event_id=payload.external_event_id,
                    payload=payload.payload,
                )
                session.add(interval)
                await session.flush()
                await session.refresh(interval)
                return self._to_busy_interval_response(interval)

    async def update_busy_interval(
        self,
        user_id: str,
        interval_id: str,
        payload: UserBusyIntervalUpdate,
    ) -> UserBusyIntervalResponse | None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                statement = select(BusyInterval).where(
                    BusyInterval.user_id == user_id,
                    BusyInterval.id == interval_id,
                    BusyInterval.schedule_id.is_(None),
                )
                interval = await session.scalar(statement)
                if interval is None:
                    return None

                patch = payload.model_dump(exclude_unset=True)
                if "start" in patch:
                    interval.start_at = patch.pop("start")
                if "end" in patch:
                    interval.end_at = patch.pop("end")
                for field_name, value in patch.items():
                    setattr(interval, field_name, value)

                await session.flush()
                await session.refresh(interval)
                return self._to_busy_interval_response(interval)

    async def delete_busy_interval(self, user_id: str, interval_id: str) -> bool:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                statement = select(BusyInterval).where(
                    BusyInterval.user_id == user_id,
                    BusyInterval.id == interval_id,
                    BusyInterval.schedule_id.is_(None),
                )
                interval = await session.scalar(statement)
                if interval is None:
                    return False

                await session.delete(interval)
                return True

    @staticmethod
    def is_unique_violation(error: IntegrityError) -> bool:
        original = getattr(error, "orig", None)
        message = str(original or error).lower()
        return "unique" in message or "duplicate" in message

    @staticmethod
    def _serialize_time_windows(windows: list[TimeWindow | dict]) -> list[dict]:
        serialized: list[dict] = []
        for window in windows:
            if isinstance(window, BaseModel):
                serialized.append(window.model_dump(mode="json"))
            else:
                serialized.append(TimeWindow.model_validate(window).model_dump(mode="json"))
        return serialized

    def _to_task_response(self, task: Task) -> UserTaskResponse:
        return UserTaskResponse(
            id=task.id,
            user_id=task.user_id,
            title=task.title,
            description=task.description,
            duration_minutes=task.duration_minutes,
            priority=task.priority,
            category=task.category,
            energy_required=task.energy_required,
            status=task.status,
            deadline=task.deadline,
            earliest_start=task.earliest_start,
            latest_end=task.latest_end,
            fixed_start=task.fixed_start,
            is_mandatory=task.is_mandatory,
            is_fixed=task.is_fixed,
            allow_splitting=task.allow_splitting,
            min_split_part_minutes=task.min_split_part_minutes,
            preferred_windows=[
                TimeWindow.model_validate(window)
                for window in (task.preferred_windows or [])
            ],
            allowed_windows=[
                TimeWindow.model_validate(window)
                for window in (task.allowed_windows or [])
            ],
            constraints=task.constraints,
            llm_metadata=task.llm_metadata,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    def _to_availability_response(
        self,
        window: AvailabilityWindow,
    ) -> AvailabilityWindowResponse:
        return AvailabilityWindowResponse(
            id=window.id,
            user_id=window.user_id,
            title=window.title,
            start=window.start_at,
            end=window.end_at,
            is_recurring=window.is_recurring,
            recurrence_rule=window.recurrence_rule,
            source=window.source,
            created_at=window.created_at,
            updated_at=window.updated_at,
        )

    def _to_busy_interval_response(
        self,
        interval: BusyInterval,
    ) -> UserBusyIntervalResponse:
        return UserBusyIntervalResponse(
            id=interval.id,
            user_id=interval.user_id,
            title=interval.title,
            start=interval.start_at,
            end=interval.end_at,
            source=interval.source,
            external_event_id=interval.external_event_id,
            payload=interval.payload,
            created_at=interval.created_at,
            updated_at=interval.updated_at,
        )
