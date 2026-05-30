from sqlalchemy import select

from backend.db.database import AsyncSessionLocal
from backend.domain.personalization.default_profiles import build_default_profile
from backend.models.personalization import UserPreferenceProfile
from backend.models.user import User, UserProfile


class PostgresUserProfileRepository:
    async def get_by_user_id(self, user_id: str) -> UserPreferenceProfile:
        async with AsyncSessionLocal() as session:
            statement = select(UserProfile).where(UserProfile.user_id == user_id)
            db_profile = await session.scalar(statement)

        if db_profile is None:
            profile = build_default_profile(user_id)
            await self.save(profile)
            return profile

        return UserPreferenceProfile.model_validate(db_profile.profile_data)

    async def save(self, profile: UserPreferenceProfile) -> None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await self._ensure_user(session, profile.user_id)
                db_profile = await session.get(UserProfile, profile.user_id)
                payload = profile.model_dump(mode="json")

                if db_profile is None:
                    session.add(
                        UserProfile(
                            user_id=profile.user_id,
                            profile_data=payload,
                        )
                    )
                else:
                    db_profile.profile_data = payload

    async def exists(self, user_id: str) -> bool:
        async with AsyncSessionLocal() as session:
            return await session.get(UserProfile, user_id) is not None

    async def delete(self, user_id: str) -> None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                db_profile = await session.get(UserProfile, user_id)
                if db_profile is not None:
                    await session.delete(db_profile)

    async def _ensure_user(self, session, user_id: str) -> None:
        db_user = await session.get(User, user_id)
        if db_user is None:
            session.add(User(id=user_id))
