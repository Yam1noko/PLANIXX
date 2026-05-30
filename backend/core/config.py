from pathlib import Path
from typing import Literal
from pydantic import field_validator
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "data"

USER_PROFILES_DIR = DATA_DIR / "user_profiles"
SCORER_CHUNKS_DIR = DATA_DIR / "scorer_chunks"


class Settings(BaseSettings):
    database_url: str
    auth_secret_key: str
    log_level: str = "INFO"
    sql_echo: bool = False
    auto_create_tables: bool = False
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout_seconds: int = 120
    cors_allow_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:9000",
        "http://127.0.0.1:9000",
    ]
    cors_allow_credentials: bool = True
    auth_access_token_ttl_minutes: int = 15
    auth_refresh_token_ttl_days: int = 30
    auth_password_hash_iterations: int = 600000
    auth_refresh_cookie_name: str = "refresh_token"
    auth_refresh_cookie_secure: bool = False
    auth_refresh_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    auth_refresh_cookie_domain: str | None = None
    auth_refresh_cookie_path: str = "/api/auth"

    model_config = SettingsConfigDict(
        env_file=(
            str(APP_DIR / ".env"),
            str(APP_DIR.parent / ".env"),
        ),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("auth_secret_key")
    @classmethod
    def validate_auth_secret_key(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("AUTH_SECRET_KEY must be at least 32 characters long.")
        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if normalized not in allowed:
            raise ValueError(
                f"LOG_LEVEL must be one of: {', '.join(sorted(allowed))}."
            )
        return normalized

    @field_validator("auth_access_token_ttl_minutes")
    @classmethod
    def validate_auth_ttl(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("AUTH_ACCESS_TOKEN_TTL_MINUTES must be positive.")
        return value

    @field_validator("auth_refresh_token_ttl_days")
    @classmethod
    def validate_refresh_ttl(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("AUTH_REFRESH_TOKEN_TTL_DAYS must be positive.")
        return value

    @field_validator("ollama_base_url")
    @classmethod
    def validate_ollama_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized:
            raise ValueError("OLLAMA_BASE_URL must not be empty.")
        return normalized

    @field_validator("ollama_timeout_seconds")
    @classmethod
    def validate_ollama_timeout_seconds(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("OLLAMA_TIMEOUT_SECONDS must be positive.")
        return value

    @field_validator("auth_password_hash_iterations")
    @classmethod
    def validate_auth_iterations(cls, value: int) -> int:
        if value < 100000:
            raise ValueError("AUTH_PASSWORD_HASH_ITERATIONS must be at least 100000.")
        return value

    @field_validator("auth_refresh_cookie_name")
    @classmethod
    def validate_refresh_cookie_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("AUTH_REFRESH_COOKIE_NAME must not be empty.")
        return value

    @field_validator("auth_refresh_cookie_path")
    @classmethod
    def validate_refresh_cookie_path(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("/"):
            raise ValueError("AUTH_REFRESH_COOKIE_PATH must start with '/'.")
        return value


settings = Settings()
