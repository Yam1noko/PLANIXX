from pydantic import BaseModel, Field


class ProductivityProfile(BaseModel):
    morning: float = Field(ge=0, le=1)
    afternoon: float = Field(ge=0, le=1)
    evening: float = Field(ge=0, le=1)
    night: float = Field(ge=0, le=1)


class LoadProfile(BaseModel):
    comfortable_daily_minutes: int = 300
    max_daily_planned_minutes: int = 480
    preferred_break_minutes: int = 15
    preferred_focus_block_minutes: int = 90
    max_focus_block_minutes: int = 120
    min_break_after_focus_minutes: int = 15


class BehaviorProfile(BaseModel):
    completion_rate: float = Field(default=0.7, ge=0, le=1)
    reschedule_rate: float = Field(default=0.25, ge=0, le=1)
    likes_compact_schedule: bool = False


class UserPreferenceProfile(BaseModel):
    user_id: str

    productivity: ProductivityProfile
    category_time_preferences: dict[str, ProductivityProfile] = Field(default_factory=dict)
    duration_multipliers: dict[str, float] = Field(default_factory=dict)
    load: LoadProfile
    behavior: BehaviorProfile


class ProductivityProfilePatch(BaseModel):
    morning: float | None = Field(default=None, ge=0, le=1)
    afternoon: float | None = Field(default=None, ge=0, le=1)
    evening: float | None = Field(default=None, ge=0, le=1)
    night: float | None = Field(default=None, ge=0, le=1)


class LoadProfilePatch(BaseModel):
    comfortable_daily_minutes: int | None = None
    max_daily_planned_minutes: int | None = None
    preferred_break_minutes: int | None = None
    preferred_focus_block_minutes: int | None = None
    max_focus_block_minutes: int | None = None
    min_break_after_focus_minutes: int | None = None


class BehaviorProfilePatch(BaseModel):
    completion_rate: float | None = Field(default=None, ge=0, le=1)
    reschedule_rate: float | None = Field(default=None, ge=0, le=1)
    likes_compact_schedule: bool | None = None


class UserPreferenceProfilePatch(BaseModel):
    productivity: ProductivityProfilePatch | None = None
    category_time_preferences: dict[str, ProductivityProfilePatch] | None = None
    duration_multipliers: dict[str, float] | None = None
    load: LoadProfilePatch | None = None
    behavior: BehaviorProfilePatch | None = None