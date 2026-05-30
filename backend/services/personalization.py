from backend.domain.personalization.default_profiles import build_default_profile
from backend.domain.personalization.solver_preferences import (
    SolverUserPreferences,
    build_solver_preferences,
)
from backend.models.personalization import (
    UserPreferenceProfile,
    UserPreferenceProfilePatch,
)
from backend.repositories.user_profiles import PostgresUserProfileRepository


class UserPreferenceService:
    def __init__(self):
        self.repository = PostgresUserProfileRepository()

    async def get_profile(self, user_id: str) -> UserPreferenceProfile:
        return await self.repository.get_by_user_id(user_id)

    async def create_default_profile(self, user_id: str) -> UserPreferenceProfile:
        profile = build_default_profile(user_id)
        await self.repository.save(profile)
        return profile

    async def save_profile(
        self,
        profile: UserPreferenceProfile,
    ) -> UserPreferenceProfile:
        await self.repository.save(profile)
        return profile

    async def delete_profile(self, user_id: str) -> None:
        await self.repository.delete(user_id)

    async def patch_profile(
        self,
        user_id: str,
        patch: UserPreferenceProfilePatch,
    ) -> UserPreferenceProfile:
        current_profile = await self.get_profile(user_id)

        current_data = current_profile.model_dump()
        patch_data = patch.model_dump(exclude_unset=True, exclude_none=True)

        merged_data = self._deep_merge(current_data, patch_data)
        merged_data["user_id"] = user_id

        updated_profile = UserPreferenceProfile.model_validate(merged_data)
        await self.repository.save(updated_profile)

        return updated_profile

    async def get_solver_preferences(self, user_id: str) -> SolverUserPreferences:
        profile = await self.get_profile(user_id)
        return build_solver_preferences(profile)

    def _deep_merge(self, base: dict, patch: dict) -> dict:
        result = dict(base)

        for key, value in patch.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result
