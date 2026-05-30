from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from backend.core.config import settings
from backend.core.security import (
    SecurityError,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    normalize_email,
    normalize_username,
    validate_password_strength,
    verify_password,
)
from backend.models.auth import (
    AccessTokenResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from backend.models.auth_session import AuthSession
from backend.models.user import User
from backend.repositories.auth_sessions import AuthSessionRepository
from backend.repositories.users import UserRepository
from backend.services.personalization import UserPreferenceService


@dataclass(slots=True)
class AuthResult:
    response: AccessTokenResponse
    refresh_token: str


class AuthService:
    def __init__(self) -> None:
        self.user_repository = UserRepository()
        self.auth_session_repository = AuthSessionRepository()
        self.preference_service = UserPreferenceService()

    async def register(
        self,
        payload: RegisterRequest,
        *,
        client_ip: str | None,
        user_agent: str | None,
    ) -> AuthResult:
        validate_password_strength(
            payload.password,
            payload.email,
            payload.username,
        )

        password_hash = hash_password(
            payload.password,
            settings.auth_password_hash_iterations,
        )

        try:
            user = await self.user_repository.create_user(
                username=payload.username,
                email=payload.email,
                password_hash=password_hash,
                timezone=payload.timezone,
                locale=payload.locale,
            )
        except IntegrityError as exc:
            if self.user_repository.is_unique_violation(exc):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A user with this email or username already exists.",
                ) from exc
            raise

        await self.preference_service.create_default_profile(user.id)
        return await self._build_auth_response(
            user,
            client_ip=client_ip,
            user_agent=user_agent,
        )

    async def login(
        self,
        payload: LoginRequest,
        *,
        client_ip: str | None,
        user_agent: str | None,
    ) -> AuthResult:
        identifier = self._normalize_identifier(payload.identifier)
        user = await self.user_repository.get_by_identifier(identifier)
        if user is None or not user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username/email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive.",
            )

        if not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username/email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = await self.user_repository.update_last_login(user.id) or user
        return await self._build_auth_response(
            user,
            client_ip=client_ip,
            user_agent=user_agent,
        )

    async def refresh(
        self,
        refresh_token: str,
        *,
        client_ip: str | None,
        user_agent: str | None,
    ) -> AuthResult:
        refresh_token_hash = hash_refresh_token(
            refresh_token,
            settings.auth_secret_key,
        )
        auth_session = await self.auth_session_repository.get_by_refresh_token_hash(
            refresh_token_hash
        )
        if auth_session is None:
            raise self._invalid_refresh_token_error()

        user = await self.user_repository.get_by_id(auth_session.user_id)
        now = datetime.now(timezone.utc)

        if user is None or not user.is_active:
            await self.auth_session_repository.revoke_family(
                auth_session.family_id,
                "user_inactive",
            )
            raise self._invalid_refresh_token_error()

        if auth_session.revoked_at is not None:
            raise self._invalid_refresh_token_error()

        if auth_session.replaced_by_session_id is not None or auth_session.rotated_at is not None:
            await self.auth_session_repository.revoke_family(
                auth_session.family_id,
                "refresh_token_reuse_detected",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token reuse detected. Please sign in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if auth_session.refresh_expires_at <= now:
            await self.auth_session_repository.revoke_session(
                auth_session.id,
                "refresh_token_expired",
            )
            raise self._invalid_refresh_token_error()

        new_refresh_token = generate_refresh_token()
        refresh_expires_at = now + timedelta(days=settings.auth_refresh_token_ttl_days)
        rotated_session = await self.auth_session_repository.rotate_session(
            current_session_id=auth_session.id,
            new_refresh_token_hash=hash_refresh_token(
                new_refresh_token,
                settings.auth_secret_key,
            ),
            refresh_expires_at=refresh_expires_at,
            used_ip=client_ip,
            used_user_agent=user_agent,
        )
        if rotated_session is None:
            raise self._invalid_refresh_token_error()

        return self._compose_auth_response(
            user,
            session=rotated_session,
            refresh_token=new_refresh_token,
            refresh_expires_at=refresh_expires_at,
        )

    async def logout_session(self, session_id: str) -> None:
        await self.auth_session_repository.revoke_session(session_id, "logout")

    async def logout_all_for_user(self, user_id: str) -> None:
        await self.auth_session_repository.revoke_all_for_user(user_id, "logout_all")

    async def get_current_user(self, access_token: str) -> User:
        user, _ = await self.authenticate_access_token(access_token)
        return user

    async def authenticate_access_token(
        self,
        access_token: str,
    ) -> tuple[User, AuthSession]:
        try:
            payload = decode_access_token(access_token, settings.auth_secret_key)
        except SecurityError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        user = await self.user_repository.get_by_id(payload["sub"])
        auth_session = await self.auth_session_repository.get_by_id(payload["sid"])
        if (
            user is None
            or not user.is_active
            or auth_session is None
            or auth_session.user_id != user.id
            or auth_session.revoked_at is not None
            or auth_session.refresh_expires_at <= datetime.now(timezone.utc)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found, inactive, or session revoked.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user, auth_session

    async def _build_auth_response(
        self,
        user: User,
        *,
        client_ip: str | None,
        user_agent: str | None,
    ) -> AuthResult:
        refresh_token = generate_refresh_token()
        refresh_expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.auth_refresh_token_ttl_days
        )
        auth_session = await self.auth_session_repository.create_session(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(
                refresh_token,
                settings.auth_secret_key,
            ),
            refresh_expires_at=refresh_expires_at,
            created_by_ip=client_ip,
            created_by_user_agent=user_agent,
        )
        return self._compose_auth_response(
            user,
            session=auth_session,
            refresh_token=refresh_token,
            refresh_expires_at=refresh_expires_at,
        )

    def _compose_auth_response(
        self,
        user: User,
        *,
        session: AuthSession,
        refresh_token: str,
        refresh_expires_at: datetime,
    ) -> AuthResult:
        if not user.email:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User record is missing an email.",
            )
        token, expires_in = create_access_token(
            user_id=user.id,
            username=user.username,
            session_id=session.id,
            secret_key=settings.auth_secret_key,
            expires_in_minutes=settings.auth_access_token_ttl_minutes,
        )
        response = AccessTokenResponse(
            access_token=token,
            expires_in=expires_in,
            refresh_expires_in=max(
                0,
                int((refresh_expires_at - datetime.now(timezone.utc)).total_seconds()),
            ),
            user=UserResponse.model_validate(user),
        )
        return AuthResult(response=response, refresh_token=refresh_token)

    def _normalize_identifier(self, identifier: str) -> str:
        if "@" in identifier:
            return normalize_email(identifier)
        return normalize_username(identifier)

    def _invalid_refresh_token_error(self) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
