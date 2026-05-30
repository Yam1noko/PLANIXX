from backend.models.personalization import (
    BehaviorProfile,
    LoadProfile,
    ProductivityProfile,
    UserPreferenceProfile,
)


def build_default_profile(user_id: str) -> UserPreferenceProfile:
    return UserPreferenceProfile(
        user_id=user_id,
        productivity=ProductivityProfile(
            morning=0.6,
            afternoon=0.75,
            evening=0.65,
            night=0.25,
        ),
        category_time_preferences={
            "study": ProductivityProfile(
                morning=0.5,
                afternoon=0.8,
                evening=0.7,
                night=0.2,
            ),
            "sport": ProductivityProfile(
                morning=0.3,
                afternoon=0.5,
                evening=0.9,
                night=0.1,
            ),
            "work": ProductivityProfile(
                morning=0.65,
                afternoon=0.8,
                evening=0.55,
                night=0.2,
            ),
            "home": ProductivityProfile(
                morning=0.55,
                afternoon=0.65,
                evening=0.7,
                night=0.25,
            ),
            "errand": ProductivityProfile(
                morning=0.6,
                afternoon=0.75,
                evening=0.55,
                night=0.1,
            ),
        },
        duration_multipliers={
            "global": 1.2,
            "study": 1.3,
            "sport": 1.2,
            "work": 1.15,
            "home": 1.1,
            "errand": 1.1,
        },
        load=LoadProfile(
            comfortable_daily_minutes=300,
            max_daily_planned_minutes=480,
            preferred_break_minutes=15,
            preferred_focus_block_minutes=90,
            max_focus_block_minutes=120,
            min_break_after_focus_minutes=15,
        ),
        behavior=BehaviorProfile(
            completion_rate=0.7,
            reschedule_rate=0.25,
            likes_compact_schedule=False,
        ),
    )
