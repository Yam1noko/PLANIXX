from pydantic import BaseModel, Field

from backend.models.personalization import UserPreferenceProfile


class SolverUserPreferences(BaseModel):
    time_block_weights: dict[str, dict[str, int]] = Field(default_factory=dict)

    global_time_block_weights: dict[str, int] = Field(default_factory=dict)

    duration_multipliers: dict[str, float] = Field(default_factory=dict)

    comfortable_daily_minutes: int
    max_daily_planned_minutes: int
    preferred_break_minutes: int
    preferred_focus_block_minutes: int
    max_focus_block_minutes: int
    min_break_after_focus_minutes: int

    completion_rate: float
    reschedule_rate: float
    likes_compact_schedule: bool


def build_solver_preferences(
    profile: UserPreferenceProfile,
) -> SolverUserPreferences:
    return SolverUserPreferences(
        time_block_weights={
            category: _productivity_to_weights(values.model_dump())
            for category, values in profile.category_time_preferences.items()
        },
        global_time_block_weights=_productivity_to_weights(
            profile.productivity.model_dump()
        ),
        duration_multipliers=profile.duration_multipliers,
        comfortable_daily_minutes=profile.load.comfortable_daily_minutes,
        max_daily_planned_minutes=profile.load.max_daily_planned_minutes,
        preferred_break_minutes=profile.load.preferred_break_minutes,
        preferred_focus_block_minutes=profile.load.preferred_focus_block_minutes,
        max_focus_block_minutes=profile.load.max_focus_block_minutes,
        min_break_after_focus_minutes=profile.load.min_break_after_focus_minutes,
        completion_rate=profile.behavior.completion_rate,
        reschedule_rate=profile.behavior.reschedule_rate,
        likes_compact_schedule=profile.behavior.likes_compact_schedule,
    )


def _productivity_to_weights(productivity: dict[str, float]) -> dict[str, int]:
    """
    Превращаем 0..1 в мягкие веса для objective.

    0.8 -> +30
    0.5 -> 0
    0.2 -> -30
    """
    result = {}

    for block_name, value in productivity.items():
        result[block_name] = int((value - 0.5) * 100)

    return result
