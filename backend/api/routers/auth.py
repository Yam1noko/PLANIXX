from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from backend.api.dependencies.auth import AuthContext, get_current_auth_context, get_current_user
from backend.core.config import settings
from backend.models.auth import (
    AccessTokenResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from backend.models.user import User
from backend.services.auth import AuthService

router = APIRouter()
service = AuthService()


@router.post("/register", response_model=AccessTokenResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
) -> AccessTokenResponse:
    result = await service.register(
        payload,
        client_ip=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _set_refresh_cookie(response, result.refresh_token, result.response.refresh_expires_in)
    return result.response


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
) -> AccessTokenResponse:
    result = await service.login(
        payload,
        client_ip=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _set_refresh_cookie(response, result.refresh_token, result.response.refresh_expires_in)
    return result.response


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request,
    response: Response,
) -> AccessTokenResponse:
    refresh_token = request.cookies.get(settings.auth_refresh_cookie_name)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token cookie is missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await service.refresh(
        refresh_token,
        client_ip=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _set_refresh_cookie(response, result.refresh_token, result.response.refresh_expires_in)
    return result.response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    context: AuthContext = Depends(get_current_auth_context),
) -> None:
    await service.logout_session(context.session.id)
    _clear_refresh_cookie(response)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    response: Response,
    context: AuthContext = Depends(get_current_auth_context),
) -> None:
    await service.logout_all_for_user(context.user.id)
    _clear_refresh_cookie(response)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


def _get_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else None


def _set_refresh_cookie(response: Response, refresh_token: str, max_age: int) -> None:
    response.set_cookie(
        key=settings.auth_refresh_cookie_name,
        value=refresh_token,
        max_age=max_age,
        httponly=True,
        secure=settings.auth_refresh_cookie_secure,
        samesite=settings.auth_refresh_cookie_samesite,
        domain=settings.auth_refresh_cookie_domain,
        path=settings.auth_refresh_cookie_path,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.auth_refresh_cookie_name,
        domain=settings.auth_refresh_cookie_domain,
        path=settings.auth_refresh_cookie_path,
        secure=settings.auth_refresh_cookie_secure,
        samesite=settings.auth_refresh_cookie_samesite,
    )
