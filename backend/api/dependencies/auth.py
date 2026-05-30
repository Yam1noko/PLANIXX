from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.models.auth_session import AuthSession
from backend.models.user import User
from backend.services.auth import AuthService


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class AuthContext:
    user: User
    session: AuthSession


async def get_current_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user, session = await AuthService().authenticate_access_token(
        credentials.credentials
    )
    return AuthContext(user=user, session=session)


async def get_current_user(
    context: AuthContext = Depends(get_current_auth_context),
) -> User:
    return context.user


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User | None:
    if credentials is None:
        return None

    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await AuthService().get_current_user(credentials.credentials)


async def get_current_session(
    context: AuthContext = Depends(get_current_auth_context),
) -> AuthSession:
    return context.session


def ensure_user_access(user_id: str, current_user: User) -> None:
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this user resource.",
        )
