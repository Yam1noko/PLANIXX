from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.core.security import normalize_email, normalize_username


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str = Field(min_length=12, max_length=128)
    timezone: str | None = Field(default=None, max_length=64)
    locale: str | None = Field(default=None, max_length=32)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return normalize_username(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        return value.strip()


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    timezone: str | None = None
    locale: str | None = None
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
    user: UserResponse
