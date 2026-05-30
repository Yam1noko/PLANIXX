from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, update

from backend.db.database import AsyncSessionLocal
from backend.models.auth_session import AuthSession


class AuthSessionRepository:
    async def get_by_id(self, session_id: str) -> AuthSession | None:
        async with AsyncSessionLocal() as session:
            return await session.get(AuthSession, session_id)

    async def get_by_refresh_token_hash(self, refresh_token_hash: str) -> AuthSession | None:
        async with AsyncSessionLocal() as session:
            statement = select(AuthSession).where(
                AuthSession.refresh_token_hash == refresh_token_hash
            )
            return await session.scalar(statement)

    async def create_session(
        self,
        *,
        user_id: str,
        refresh_token_hash: str,
        refresh_expires_at: datetime,
        created_by_ip: str | None,
        created_by_user_agent: str | None,
        family_id: str | None = None,
    ) -> AuthSession:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                auth_session = AuthSession(
                    user_id=user_id,
                    family_id=family_id or str(uuid4()),
                    refresh_token_hash=refresh_token_hash,
                    created_by_ip=created_by_ip,
                    created_by_user_agent=created_by_user_agent,
                    last_used_at=datetime.now(timezone.utc),
                    last_used_ip=created_by_ip,
                    last_used_user_agent=created_by_user_agent,
                    refresh_expires_at=refresh_expires_at,
                )
                session.add(auth_session)
                await session.flush()
                await session.refresh(auth_session)
                return auth_session

    async def rotate_session(
        self,
        *,
        current_session_id: str,
        new_refresh_token_hash: str,
        refresh_expires_at: datetime,
        used_ip: str | None,
        used_user_agent: str | None,
    ) -> AuthSession | None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                current_session = await session.get(AuthSession, current_session_id)
                if current_session is None:
                    return None

                now = datetime.now(timezone.utc)
                current_session.last_used_at = now
                current_session.last_used_ip = used_ip
                current_session.last_used_user_agent = used_user_agent

                rotated_session = AuthSession(
                    user_id=current_session.user_id,
                    family_id=current_session.family_id,
                    refresh_token_hash=new_refresh_token_hash,
                    created_by_ip=used_ip or current_session.created_by_ip,
                    created_by_user_agent=used_user_agent or current_session.created_by_user_agent,
                    last_used_at=now,
                    last_used_ip=used_ip,
                    last_used_user_agent=used_user_agent,
                    refresh_expires_at=refresh_expires_at,
                )
                session.add(rotated_session)
                await session.flush()

                current_session.rotated_at = now
                current_session.replaced_by_session_id = rotated_session.id

                await session.flush()
                await session.refresh(rotated_session)
                return rotated_session

    async def touch_session(
        self,
        session_id: str,
        *,
        used_ip: str | None,
        used_user_agent: str | None,
    ) -> None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                db_session = await session.get(AuthSession, session_id)
                if db_session is None:
                    return

                db_session.last_used_at = datetime.now(timezone.utc)
                db_session.last_used_ip = used_ip
                db_session.last_used_user_agent = used_user_agent

    async def revoke_session(self, session_id: str, reason: str) -> None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                db_session = await session.get(AuthSession, session_id)
                if db_session is None or db_session.revoked_at is not None:
                    return

                db_session.revoked_at = datetime.now(timezone.utc)
                db_session.revoke_reason = reason

    async def revoke_family(self, family_id: str, reason: str) -> None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await session.execute(
                    update(AuthSession)
                    .where(
                        AuthSession.family_id == family_id,
                        AuthSession.revoked_at.is_(None),
                    )
                    .values(
                        revoked_at=datetime.now(timezone.utc),
                        revoke_reason=reason,
                    )
                )

    async def revoke_all_for_user(self, user_id: str, reason: str) -> None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await session.execute(
                    update(AuthSession)
                    .where(
                        AuthSession.user_id == user_id,
                        AuthSession.revoked_at.is_(None),
                    )
                    .values(
                        revoked_at=datetime.now(timezone.utc),
                        revoke_reason=reason,
                    )
                )
