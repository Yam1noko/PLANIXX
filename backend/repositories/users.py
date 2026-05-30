from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from backend.db.database import AsyncSessionLocal
from backend.models.user import User


class UserRepository:
    async def get_by_id(self, user_id: str) -> User | None:
        async with AsyncSessionLocal() as session:
            return await session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        async with AsyncSessionLocal() as session:
            statement = select(User).where(User.email == email)
            return await session.scalar(statement)

    async def get_by_username(self, username: str) -> User | None:
        async with AsyncSessionLocal() as session:
            statement = select(User).where(User.username == username)
            return await session.scalar(statement)

    async def get_by_identifier(self, identifier: str) -> User | None:
        async with AsyncSessionLocal() as session:
            statement = select(User).where(
                or_(User.email == identifier, User.username == identifier)
            )
            return await session.scalar(statement)

    async def create_user(
        self,
        *,
        username: str,
        email: str,
        password_hash: str,
        timezone: str | None,
        locale: str | None,
    ) -> User:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                user = User(
                    id=str(uuid4()),
                    username=username,
                    email=email,
                    password_hash=password_hash,
                    timezone=timezone,
                    locale=locale,
                    is_active=True,
                )
                session.add(user)
                await session.flush()
                await session.refresh(user)
                return user

    async def update_last_login(self, user_id: str) -> User | None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                user = await session.get(User, user_id)
                if user is None:
                    return None

                user.last_login_at = datetime.now(timezone.utc)
                await session.flush()
                await session.refresh(user)
                return user

    @staticmethod
    def is_unique_violation(error: IntegrityError) -> bool:
        original = getattr(error, "orig", None)
        message = str(original or error).lower()
        return "unique" in message and ("email" in message or "username" in message)
