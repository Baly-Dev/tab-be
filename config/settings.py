"""Central settings loaded from environment and ``.env`` / ``.env.local`` files."""

from functools import lru_cache
from typing import Literal, Self
from urllib.parse import quote_plus

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SYNC_DRIVER = "psycopg"
_ASYNC_DRIVER = "asyncpg"


def sqlalchemy_database_url(url: str, *, driver: str = _SYNC_DRIVER) -> str:
    """Normalize ``postgres(ql)://`` URLs to SQLAlchemy + driver.

    Leaves URLs that already include a dialect driver (``postgresql+psycopg://``)
    unchanged. Query params such as ``sslmode=require`` are preserved.
    """
    raw = url.strip()
    if not raw:
        return raw
    scheme, sep, rest = raw.partition("://")
    if not sep:
        return raw
    base, _, current_driver = scheme.partition("+")
    if current_driver:
        return raw
    if base not in ("postgres", "postgresql"):
        return raw
    return f"postgresql+{driver}://{rest}"


class Settings(BaseSettings):
    """Runtime configuration. DB_* for Postgres; ``DATABASE_URL`` optional full override."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["local", "development", "staging", "production"] = "local"
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    sentry_dsn: str = Field(default="", validation_alias="SENTRY_DSN")
    sentry_environment: str = Field(
        default="",
        validation_alias="SENTRY_ENVIRONMENT",
        description="Override environment tag in Sentry; empty = APP_ENV.",
    )
    sentry_release: str = Field(
        default="",
        validation_alias="SENTRY_RELEASE",
        description="Override release; empty = tab-intranet@<package version>.",
    )
    sentry_traces_sample_rate: float | None = Field(
        default=None,
        validation_alias="SENTRY_TRACES_SAMPLE_RATE",
    )
    sentry_profile_session_sample_rate: float | None = Field(
        default=None,
        validation_alias="SENTRY_PROFILE_SESSION_SAMPLE_RATE",
    )

    @field_validator(
        "sentry_traces_sample_rate",
        "sentry_profile_session_sample_rate",
        mode="before",
    )
    @classmethod
    def empty_sentry_rate_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_sync_database_url(cls, value: object) -> object:
        if isinstance(value, str) and value.strip():
            return sqlalchemy_database_url(value, driver=_SYNC_DRIVER)
        return value

    @field_validator("database_url_async", mode="before")
    @classmethod
    def normalize_async_database_url(cls, value: object) -> object:
        if isinstance(value, str) and value.strip():
            return sqlalchemy_database_url(value, driver=_ASYNC_DRIVER)
        return value

    db_host: str = Field(default="localhost", validation_alias="DB_HOST")
    db_port: int = Field(default=5434, validation_alias="DB_PORT")
    db_user: str = Field(default="postgres", validation_alias="DB_USER")
    db_password: str = Field(default="postgres", validation_alias="DB_PASSWORD")
    db_name: str = Field(default="tab_intranet", validation_alias="DB_NAME")

    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    database_url_async: str | None = Field(default=None, validation_alias="DATABASE_URL_ASYNC")

    jwt_secret: str = Field(default="", validation_alias="JWT_SECRET")
    jwt_access_token_expire_minutes: int = Field(
        default=15,
        validation_alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
    )
    jwt_refresh_token_expire_days: int = Field(
        default=30,
        validation_alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS",
    )

    redis_url: str = Field(
        default="redis://localhost:6381/0",
        validation_alias="REDIS_URL",
    )
    refresh_token_store: Literal["redis", "postgres"] = Field(
        default="redis",
        validation_alias="REFRESH_TOKEN_STORE",
        description="redis = refresh sessions in Redis; postgres = auth_refresh_token.",
    )
    email_verify_token_expire_hours: int = Field(
        default=72,
        validation_alias="EMAIL_VERIFY_TOKEN_EXPIRE_HOURS",
    )

    brevo_api_key: str = Field(default="", validation_alias="BREVO_API_KEY")
    brevo_email_verification_template_id: int = Field(
        default=0,
        validation_alias="BREVO_EMAIL_VERIFICATION_TEMPLATE_ID",
    )
    brevo_email_verification_link_param: str = Field(
        default="verification_url",
        validation_alias="BREVO_EMAIL_VERIFICATION_LINK_PARAM",
    )
    brevo_email_verification_first_name_param: str = Field(
        default="first_name",
        validation_alias="BREVO_EMAIL_VERIFICATION_FIRST_NAME_PARAM",
    )
    email_sender_email: str = Field(default="", validation_alias="EMAIL_SENDER_EMAIL")
    email_sender_name: str = Field(default="Tab Intranet", validation_alias="EMAIL_SENDER_NAME")
    email_verification_frontend_url: str = Field(
        default="http://localhost:3000/auth/verify-email",
        validation_alias="EMAIL_VERIFICATION_FRONTEND_URL",
    )
    app_frontend_url: str = Field(
        default="http://localhost:3000",
        validation_alias="APP_FRONTEND_URL",
        description="Frontend origin used by the welcome email.",
    )

    google_oauth_client_id: str = Field(default="", validation_alias="GOOGLE_OAUTH_CLIENT_ID")
    google_oauth_client_secret: str = Field(
        default="",
        validation_alias="GOOGLE_OAUTH_CLIENT_SECRET",
    )
    google_oauth_redirect_uri: str = Field(
        default="http://127.0.0.1:8002/api/v1/auth/google/callback",
        validation_alias="GOOGLE_OAUTH_REDIRECT_URI",
    )
    google_oauth_frontend_callback_url: str = Field(
        default="http://localhost:3000/auth/google/callback",
        validation_alias="GOOGLE_OAUTH_FRONTEND_CALLBACK_URL",
    )
    google_oauth_state_expire_minutes: int = Field(
        default=10,
        validation_alias="GOOGLE_OAUTH_STATE_EXPIRE_MINUTES",
    )

    linkedin_oauth_client_id: str = Field(default="", validation_alias="LINKEDIN_OAUTH_CLIENT_ID")
    linkedin_oauth_client_secret: str = Field(
        default="",
        validation_alias="LINKEDIN_OAUTH_CLIENT_SECRET",
    )
    linkedin_oauth_redirect_uri: str = Field(
        default="http://127.0.0.1:8002/api/v1/auth/linkedin/callback",
        validation_alias="LINKEDIN_OAUTH_REDIRECT_URI",
    )
    linkedin_oauth_frontend_callback_url: str = Field(
        default="http://localhost:3000/auth/linkedin/callback",
        validation_alias="LINKEDIN_OAUTH_FRONTEND_CALLBACK_URL",
    )
    linkedin_oauth_state_expire_minutes: int = Field(
        default=10,
        validation_alias="LINKEDIN_OAUTH_STATE_EXPIRE_MINUTES",
    )

    webauthn_rp_id: str = Field(default="localhost", validation_alias="WEBAUTHN_RP_ID")
    webauthn_rp_name: str = Field(default="Tab Intranet", validation_alias="WEBAUTHN_RP_NAME")
    webauthn_origin: str = Field(
        default="http://localhost:3000",
        validation_alias="WEBAUTHN_ORIGIN",
    )
    webauthn_challenge_expire_minutes: int = Field(
        default=5,
        validation_alias="WEBAUTHN_CHALLENGE_EXPIRE_MINUTES",
    )

    password_reset_frontend_url: str = Field(
        default="http://localhost:3000/reset-password",
        validation_alias="PASSWORD_RESET_FRONTEND_URL",
    )
    password_reset_token_expire_minutes: int = Field(
        default=60,
        validation_alias="PASSWORD_RESET_TOKEN_EXPIRE_MINUTES",
    )
    password_reset_rate_limit_per_hour: int = Field(
        default=5,
        validation_alias="PASSWORD_RESET_RATE_LIMIT_PER_HOUR",
    )
    brevo_password_reset_template_id: int = Field(
        default=0,
        validation_alias="BREVO_PASSWORD_RESET_TEMPLATE_ID",
    )
    brevo_password_reset_link_param: str = Field(
        default="reset_url",
        validation_alias="BREVO_PASSWORD_RESET_LINK_PARAM",
    )
    brevo_password_reset_first_name_param: str = Field(
        default="first_name",
        validation_alias="BREVO_PASSWORD_RESET_FIRST_NAME_PARAM",
    )

    brevo_welcome_template_id: int = Field(
        default=0,
        validation_alias="BREVO_WELCOME_TEMPLATE_ID",
    )
    brevo_welcome_first_name_param: str = Field(
        default="first_name",
        validation_alias="BREVO_WELCOME_FIRST_NAME_PARAM",
    )
    brevo_welcome_link_param: str = Field(
        default="app_url",
        validation_alias="BREVO_WELCOME_LINK_PARAM",
    )

    @property
    def uses_redis_refresh_store(self) -> bool:
        return self.refresh_token_store.strip().lower() == "redis"

    @property
    def refresh_token_ttl_seconds(self) -> int:
        return max(1, self.jwt_refresh_token_expire_days * 86_400)

    @model_validator(mode="after")
    def ensure_database_url(self) -> Self:
        if self.database_url.strip():
            object.__setattr__(
                self,
                "database_url",
                sqlalchemy_database_url(self.database_url, driver=_SYNC_DRIVER),
            )
            return self
        u = quote_plus(self.db_user)
        p = quote_plus(self.db_password)
        url = f"postgresql+{_SYNC_DRIVER}://{u}:{p}@{self.db_host}:{self.db_port}/{self.db_name}"
        object.__setattr__(self, "database_url", url)
        return self

    @model_validator(mode="after")
    def validate_redis_refresh_store(self) -> Self:
        if self.uses_redis_refresh_store and not self.redis_url.strip():
            raise ValueError("REDIS_URL is required when REFRESH_TOKEN_STORE=redis")
        return self

    @model_validator(mode="after")
    def require_jwt_secret_outside_local(self) -> Self:
        if self.app_env in ("staging", "production") and not self.jwt_secret.strip():
            raise ValueError("JWT_SECRET is required when APP_ENV is staging or production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
