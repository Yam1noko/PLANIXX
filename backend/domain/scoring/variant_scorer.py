from collections import defaultdict
from datetime import datetime

from backend.domain.personalization.default_profiles import build_default_profile
from backend.models.personalization import ProductivityProfile, UserPreferenceProfile
from backend.models.scoring import (
    BestVariantSelectionResponse,
    SolverResultChunk,
    SolverResultChunkingResponse,
    VariantScoreBreakdown,
)
from backend.models.scheduling import ScheduledTask, TaskInput



# Main score weights. Keep them at the top so they can be tuned manually.
W_COMPLETION = 0.30
W_PRIORITY = 0.25
W_TIME_PREFERENCE = 0.15
W_PRODUCTIVITY = 0.15
W_LOAD = 0.10
W_FOCUS_STRUCTURE = 0.05


# Penalty weights. Keep them separate from the main weighted sum.
PENALTY_MANDATORY_UNSCHEDULED = 0.20
PENALTY_PER_VIOLATION = 0.03


class SolverVariantScorer:
    def select_best_variant(
        self,
        response: SolverResultChunkingResponse,
    ) -> BestVariantSelectionResponse:
        if not response.chunks:
            raise ValueError("Chunking response does not contain variants to score.")

        scored_chunks: list[SolverResultChunk] = []
        variant_scores: list[VariantScoreBreakdown] = []

        for chunk in response.chunks:
            breakdown = self._score_chunk(chunk)
            scored_chunk = chunk.model_copy(deep=True)
            scored_chunk.schedule_variant.score = breakdown.total_score
            scored_chunk.metadata = {
                **scored_chunk.metadata,
                "scoring": breakdown.model_dump(),
            }

            scored_chunks.append(scored_chunk)
            variant_scores.append(breakdown)

        best_chunk = max(
            scored_chunks,
            key=lambda chunk: (
                chunk.schedule_variant.score or float("-inf"),
                -chunk.schedule_variant.variant_id,
            ),
        )

        return BestVariantSelectionResponse(
            batch_id=response.batch_id,
            chunk_id=best_chunk.chunk_id,
            best_variant_id=best_chunk.schedule_variant.variant_id,
            selected_chunk=best_chunk,
            variant_scores=variant_scores,
        )

    def _score_chunk(self, chunk: SolverResultChunk) -> VariantScoreBreakdown:
        profile = self._resolve_profile(chunk)
        all_tasks = self._get_all_tasks(chunk)
        scheduled_tasks = chunk.schedule_variant.scheduled_tasks

        completion_score = self._compute_completion_score(all_tasks, scheduled_tasks)
        priority_score = self._compute_priority_score(all_tasks, scheduled_tasks)
        time_preference_score = self._compute_time_preference_score(
            profile,
            scheduled_tasks,
        )
        productivity_score = self._compute_productivity_score(profile, scheduled_tasks)
        load_score = self._compute_load_score(profile, scheduled_tasks)
        focus_structure_score, bad_blocks_count, total_blocks_count = (
            self._compute_focus_structure_score(profile, scheduled_tasks)
        )
        mandatory_unscheduled_penalty = self._compute_mandatory_unscheduled_penalty(
            all_tasks,
            chunk,
        )
        violation_penalty = PENALTY_PER_VIOLATION * len(chunk.violations)
        penalties = mandatory_unscheduled_penalty + violation_penalty

        total_score = (
            W_COMPLETION * completion_score
            + W_PRIORITY * priority_score
            + W_TIME_PREFERENCE * time_preference_score
            + W_PRODUCTIVITY * productivity_score
            + W_LOAD * load_score
            + W_FOCUS_STRUCTURE * focus_structure_score
            - penalties
        )

        return VariantScoreBreakdown(
            variant_id=chunk.schedule_variant.variant_id,
            total_score=round(total_score, 4),
            completion_score=round(completion_score, 4),
            priority_score=round(priority_score, 4),
            time_preference_score=round(time_preference_score, 4),
            productivity_score=round(productivity_score, 4),
            load_score=round(load_score, 4),
            focus_structure_score=round(focus_structure_score, 4),
            penalties=round(penalties, 4),
            mandatory_unscheduled_penalty=round(mandatory_unscheduled_penalty, 4),
            violation_penalty=round(violation_penalty, 4),
            bad_blocks_count=bad_blocks_count,
            total_blocks_count=total_blocks_count,
            scheduled_tasks_count=len(scheduled_tasks),
            unscheduled_tasks_count=len(chunk.schedule_variant.unscheduled_tasks),
        )

    def _resolve_profile(self, chunk: SolverResultChunk) -> UserPreferenceProfile:
        if chunk.profile_context.profile is not None:
            return chunk.profile_context.profile

        user_id = (
            chunk.profile_context.user_id
            or (chunk.source_request.user_id if chunk.source_request else None)
            or "scorer"
        )
        return build_default_profile(user_id)

    def _get_all_tasks(self, chunk: SolverResultChunk) -> list[TaskInput]:
        if chunk.source_request is not None:
            return chunk.source_request.tasks

        tasks_by_id: dict[str, TaskInput] = {}

        for scheduled_task in chunk.schedule_variant.scheduled_tasks:
            tasks_by_id[scheduled_task.task.id] = scheduled_task.task

        for unscheduled_task in chunk.schedule_variant.unscheduled_tasks:
            tasks_by_id[unscheduled_task.task.id] = unscheduled_task.task

        return list(tasks_by_id.values())

    def _compute_completion_score(
        self,
        all_tasks: list[TaskInput],
        scheduled_tasks: list[ScheduledTask],
    ) -> float:
        total_requested_minutes = sum(task.duration_minutes for task in all_tasks)
        total_scheduled_minutes = sum(task.duration_minutes for task in scheduled_tasks)

        if total_requested_minutes == 0:
            return 1.0

        return total_scheduled_minutes / total_requested_minutes

    def _compute_priority_score(
        self,
        all_tasks: list[TaskInput],
        scheduled_tasks: list[ScheduledTask],
    ) -> float:
        total_priority = sum(task.priority for task in all_tasks)
        scheduled_priority = sum(task.priority for task in scheduled_tasks)

        if total_priority == 0:
            return 1.0

        return scheduled_priority / total_priority

    def _compute_time_preference_score(
        self,
        profile: UserPreferenceProfile,
        scheduled_tasks: list[ScheduledTask],
    ) -> float:
        if not scheduled_tasks:
            return 0.0

        scores = [
            self._get_category_time_preference(profile, task.task.category, task.start)
            for task in scheduled_tasks
        ]
        return sum(scores) / len(scores)

    def _compute_productivity_score(
        self,
        profile: UserPreferenceProfile,
        scheduled_tasks: list[ScheduledTask],
    ) -> float:
        weighted_score = 0.0
        total_priority = 0

        for task in scheduled_tasks:
            productivity = self._get_profile_value(
                profile.productivity,
                self._get_time_block(task.start),
            )
            weighted_score += task.priority * productivity
            total_priority += task.priority

        if total_priority == 0:
            return 0.0

        return weighted_score / total_priority

    def _compute_load_score(
        self,
        profile: UserPreferenceProfile,
        scheduled_tasks: list[ScheduledTask],
    ) -> float:
        if not scheduled_tasks:
            return 0.0

        daily_minutes: dict[str, int] = defaultdict(int)
        comfortable = profile.load.comfortable_daily_minutes
        maximum = profile.load.max_daily_planned_minutes

        for task in scheduled_tasks:
            daily_minutes[task.start.date().isoformat()] += task.duration_minutes

        day_scores = [
            self._compute_day_load_score(comfortable, maximum, minutes)
            for minutes in daily_minutes.values()
        ]
        return sum(day_scores) / len(day_scores)

    def _compute_focus_structure_score(
        self,
        profile: UserPreferenceProfile,
        scheduled_tasks: list[ScheduledTask],
    ) -> tuple[float, int, int]:
        if not scheduled_tasks:
            return 0.0, 0, 0

        bad_blocks_count = 0
        total_blocks_count = len(scheduled_tasks)
        sorted_tasks = sorted(scheduled_tasks, key=lambda task: (task.start, task.end))

        for task in sorted_tasks:
            if task.duration_minutes > profile.load.max_focus_block_minutes:
                bad_blocks_count += 1

        for previous_task, next_task in zip(sorted_tasks, sorted_tasks[1:]):
            total_blocks_count += 1
            gap_minutes = int((next_task.start - previous_task.end).total_seconds() // 60)

            if (
                previous_task.duration_minutes >= profile.load.preferred_focus_block_minutes
                and gap_minutes < profile.load.min_break_after_focus_minutes
            ):
                bad_blocks_count += 1

        focus_score = 1 - (bad_blocks_count / total_blocks_count)
        return max(0.0, focus_score), bad_blocks_count, total_blocks_count

    def _compute_mandatory_unscheduled_penalty(
        self,
        all_tasks: list[TaskInput],
        chunk: SolverResultChunk,
    ) -> float:
        mandatory_total = sum(1 for task in all_tasks if task.is_mandatory)
        mandatory_unscheduled = sum(
            1
            for task in chunk.schedule_variant.unscheduled_tasks
            if task.task.is_mandatory
        )

        if mandatory_total == 0:
            return 0.0

        return PENALTY_MANDATORY_UNSCHEDULED * (
            mandatory_unscheduled / mandatory_total
        )

    def _compute_day_load_score(
        self,
        comfortable_minutes: int,
        max_minutes: int,
        daily_minutes: int,
    ) -> float:
        if daily_minutes <= comfortable_minutes:
            return 1.0

        if max_minutes <= comfortable_minutes:
            return 0.0 if daily_minutes > comfortable_minutes else 1.0

        if daily_minutes <= max_minutes:
            return 1 - (
                (daily_minutes - comfortable_minutes)
                / (max_minutes - comfortable_minutes)
            )

        return 0.0

    def _get_category_time_preference(
        self,
        profile: UserPreferenceProfile,
        category: str | None,
        start: datetime,
    ) -> float:
        time_block = self._get_time_block(start)
        category_profile = (
            profile.category_time_preferences.get(category)
            if category is not None
            else None
        )

        if category_profile is not None:
            return self._get_profile_value(category_profile, time_block)

        return self._get_profile_value(profile.productivity, time_block)

    def _get_profile_value(
        self,
        profile: ProductivityProfile,
        time_block: str,
    ) -> float:
        return float(getattr(profile, time_block, 0.5))

    def _get_time_block(self, value: datetime) -> str:
        hour = value.hour

        if 6 <= hour < 12:
            return "morning"

        if 12 <= hour < 18:
            return "afternoon"

        if 18 <= hour < 23:
            return "evening"

        return "night"
