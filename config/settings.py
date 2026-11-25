"""Central settings loaded from environment and ``.env`` / ``.env.local`` files."""

from functools import lru_cache
from typing import Literal, Self
from urllib.parse import quote_plus

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SYNC_DRIVER = "psycopg"
_ASYNC_DRIVER = "asyncpg"


def sqlalchemy_database_url(url: str, *, driver: str = _SYNC_DRIVER) -> str:
    """Normalize Railway/Heroku ``postgres(ql)://`` URLs to SQLAlchemy + driver.

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
    """Runtime configuration. DB_* per Postgres; ``DATABASE_URL`` opzionale (override completo)."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # APP
    app_env: Literal["local", "development", "staging", "production"] = "local"
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # SENTRY
    sentry_dsn: str = Field(default="", validation_alias="SENTRY_DSN")
    sentry_environment: str = Field(
        default="",
        validation_alias="SENTRY_ENVIRONMENT",
        description="Override environment tag in Sentry; empty = APP_ENV.",
    )
    sentry_release: str = Field(
        default="",
        validation_alias="SENTRY_RELEASE",
        description="Override release; empty = tn-be@<package version>.",
    )
    sentry_traces_sample_rate: float | None = Field(
        default=None,
        validation_alias="SENTRY_TRACES_SAMPLE_RATE",
        description="Override traces sample rate (0–1). Empty = default by APP_ENV.",
    )
    sentry_profile_session_sample_rate: float | None = Field(
        default=None,
        validation_alias="SENTRY_PROFILE_SESSION_SAMPLE_RATE",
        description="Override continuous profiling rate (0–1). Empty = default by APP_ENV.",
    )

    @field_validator("sentry_traces_sample_rate", "sentry_profile_session_sample_rate", mode="before")
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

    # DATABASE
    db_host: str = Field(default="localhost", validation_alias="DB_HOST")
    db_port: int = Field(default=5432, validation_alias="DB_PORT")
    db_user: str = Field(default="postgres", validation_alias="DB_USER")
    db_password: str = Field(default="postgres", validation_alias="DB_PASSWORD")
    db_name: str = Field(default="tn_be", validation_alias="DB_NAME")

    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    database_url_async: str | None = Field(default=None, validation_alias="DATABASE_URL_ASYNC")

    # AUTH
    jwt_secret: str = Field(default="", validation_alias="JWT_SECRET")
    jwt_access_token_expire_minutes: int = Field(
        default=15,
        validation_alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
    )
    jwt_refresh_token_expire_days: int = Field(
        default=30,
        validation_alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS",
    )

    # REDIS (refresh session / opzionale rate limit)
    redis_url: str = Field(default="", validation_alias="REDIS_URL")
    refresh_token_store: Literal["redis", "postgres"] = Field(
        default="redis",
        validation_alias="REFRESH_TOKEN_STORE",
        description="redis = sessioni refresh su Redis; postgres = legacy auth_refresh_token.",
    )
    email_verify_token_expire_hours: int = Field(
        default=72,
        validation_alias="EMAIL_VERIFY_TOKEN_EXPIRE_HOURS",
    )

    # BREVO
    brevo_api_key: str = Field(default="", validation_alias="BREVO_API_KEY")
    brevo_email_verification_template_id: int = Field(
        default=0,
        validation_alias="BREVO_EMAIL_VERIFICATION_TEMPLATE_ID",
        description="ID numerico del template transazionale Brevo per la verifica email.",
    )
    brevo_email_verification_link_param: str = Field(
        default="verification_url",
        validation_alias="BREVO_EMAIL_VERIFICATION_LINK_PARAM",
        description="Chiave in params (es. {{ params.verification_url }} nel template Brevo).",
    )
    brevo_email_verification_first_name_param: str = Field(
        default="first_name",
        validation_alias="BREVO_EMAIL_VERIFICATION_FIRST_NAME_PARAM",
        description="Chiave per il nome nel template; stringa vuota = non inviare.",
    )
    email_sender_email: str = Field(default="", validation_alias="EMAIL_SENDER_EMAIL")
    email_sender_name: str = Field(default="Financ&youth", validation_alias="EMAIL_SENDER_NAME")
    email_verification_frontend_url: str = Field(
        default="http://localhost:3000/auth/verify-email",
        validation_alias="EMAIL_VERIFICATION_FRONTEND_URL",
        description="URL FE con query ?token= (link nell'email).",
    )

    # GOOGLE OAUTH
    google_oauth_client_id: str = Field(default="", validation_alias="GOOGLE_OAUTH_CLIENT_ID")
    google_oauth_client_secret: str = Field(
        default="",
        validation_alias="GOOGLE_OAUTH_CLIENT_SECRET",
    )
    google_oauth_redirect_uri: str = Field(
        default="http://127.0.0.1:8000/api/v1/auth/google/callback",
        validation_alias="GOOGLE_OAUTH_REDIRECT_URI",
        description="Redirect URI registrata in Google Cloud (callback backend).",
    )
    google_oauth_frontend_callback_url: str = Field(
        default="http://localhost:3000/auth/google/callback",
        validation_alias="GOOGLE_OAUTH_FRONTEND_CALLBACK_URL",
        description="Dopo OAuth, redirect browser con token in query (FE legge e pulisce URL).",
    )
    google_oauth_state_expire_minutes: int = Field(
        default=10,
        validation_alias="GOOGLE_OAUTH_STATE_EXPIRE_MINUTES",
    )

    # LINKEDIN OAUTH (Sign In with LinkedIn using OpenID Connect)
    linkedin_oauth_client_id: str = Field(default="", validation_alias="LINKEDIN_OAUTH_CLIENT_ID")
    linkedin_oauth_client_secret: str = Field(
        default="",
        validation_alias="LINKEDIN_OAUTH_CLIENT_SECRET",
    )
    linkedin_oauth_redirect_uri: str = Field(
        default="http://127.0.0.1:8000/api/v1/auth/linkedin/callback",
        validation_alias="LINKEDIN_OAUTH_REDIRECT_URI",
        description="Redirect URI registrata in LinkedIn Developer App (callback backend).",
    )
    linkedin_oauth_frontend_callback_url: str = Field(
        default="http://localhost:3000/auth/linkedin/callback",
        validation_alias="LINKEDIN_OAUTH_FRONTEND_CALLBACK_URL",
        description="Dopo OAuth LinkedIn, redirect browser con token in query.",
    )
    linkedin_oauth_state_expire_minutes: int = Field(
        default=10,
        validation_alias="LINKEDIN_OAUTH_STATE_EXPIRE_MINUTES",
    )

    # WEBAUTHN / PASSKEYS (RP ID = hostname del frontend che l'utente vede)
    webauthn_rp_id: str = Field(
        default="localhost",
        validation_alias="WEBAUTHN_RP_ID",
        description="Hostname Relying Party (es. localhost, app.trustnet.it). Non include lo schema.",
    )
    webauthn_rp_name: str = Field(
        default="Financ&youth",
        validation_alias="WEBAUTHN_RP_NAME",
    )
    webauthn_origin: str = Field(
        default="http://localhost:3000",
        validation_alias="WEBAUTHN_ORIGIN",
        description="Origin esatto del frontend (schema + host + porta). Face ID/passkey partono da qui.",
    )
    webauthn_challenge_expire_minutes: int = Field(
        default=5,
        validation_alias="WEBAUTHN_CHALLENGE_EXPIRE_MINUTES",
    )

    # PASSWORD RESET
    password_reset_frontend_url: str = Field(
        default="http://localhost:3000/reset-password",
        validation_alias="PASSWORD_RESET_FRONTEND_URL",
        description="URL FE con query ?token= (link email reset password).",
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

    # EVENT REGISTRATION EMAILS
    event_detail_frontend_url: str = Field(
        default="http://localhost:3000/events",
        validation_alias="EVENT_DETAIL_FRONTEND_URL",
        description="Base URL FE pagina dettaglio evento (link nelle email).",
    )
    brevo_event_confirmation_request_template_id: int = Field(
        default=0,
        validation_alias="BREVO_EVENT_CONFIRMATION_REQUEST_TEMPLATE_ID",
    )
    brevo_event_confirmation_reminder_template_id: int = Field(
        default=0,
        validation_alias="BREVO_EVENT_CONFIRMATION_REMINDER_TEMPLATE_ID",
    )
    brevo_event_confirmation_followup_template_id: int = Field(
        default=0,
        validation_alias="BREVO_EVENT_CONFIRMATION_FOLLOWUP_TEMPLATE_ID",
    )
    brevo_event_confirmation_expired_template_id: int = Field(
        default=0,
        validation_alias="BREVO_EVENT_CONFIRMATION_EXPIRED_TEMPLATE_ID",
    )
    brevo_event_waitlist_promoted_template_id: int = Field(
        default=0,
        validation_alias="BREVO_EVENT_WAITLIST_PROMOTED_TEMPLATE_ID",
    )
    brevo_event_reminder_template_id: int = Field(
        default=0,
        validation_alias="BREVO_EVENT_REMINDER_TEMPLATE_ID",
    )
    brevo_event_waitlist_joined_template_id: int = Field(
        default=0,
        validation_alias="BREVO_EVENT_WAITLIST_JOINED_TEMPLATE_ID",
    )
    brevo_event_registration_auto_cancelled_template_id: int = Field(
        default=0,
        validation_alias="BREVO_EVENT_REGISTRATION_AUTO_CANCELLED_TEMPLATE_ID",
    )
    brevo_event_registration_system_cancelled_template_id: int = Field(
        default=0,
        validation_alias="BREVO_EVENT_REGISTRATION_SYSTEM_CANCELLED_TEMPLATE_ID",
    )
    brevo_event_registration_confirmed_template_id: int = Field(
        default=0,
        validation_alias="BREVO_EVENT_REGISTRATION_CONFIRMED_TEMPLATE_ID",
    )
    brevo_event_link_param: str = Field(
        default="event_url",
        validation_alias="BREVO_EVENT_LINK_PARAM",
    )
    brevo_event_first_name_param: str = Field(
        default="first_name",
        validation_alias="BREVO_EVENT_FIRST_NAME_PARAM",
    )
    brevo_event_title_param: str = Field(
        default="event_title",
        validation_alias="BREVO_EVENT_TITLE_PARAM",
    )

    # WELCOME EMAIL (registrazione completata)
    brevo_welcome_template_id: int = Field(
        default=0,
        validation_alias="BREVO_WELCOME_TEMPLATE_ID",
        description="Template transazionale dopo verifica email o completamento wizard OAuth.",
    )
    brevo_welcome_first_name_param: str = Field(
        default="first_name",
        validation_alias="BREVO_WELCOME_FIRST_NAME_PARAM",
    )
    brevo_welcome_link_param: str = Field(
        default="app_url",
        validation_alias="BREVO_WELCOME_LINK_PARAM",
    )

    # CONNECTION + EVENT BELL (ID 0 = invio saltato finché il template non è pronto)
    brevo_connection_request_template_id: int = Field(
        default=0,
        validation_alias="BREVO_CONNECTION_REQUEST_TEMPLATE_ID",
        description="Template Brevo per la richiesta di connessione.",
    )
    brevo_connection_event_registered_template_id: int = Field(
        default=0,
        validation_alias="BREVO_CONNECTION_EVENT_REGISTERED_TEMPLATE_ID",
        description="Template Brevo per la campanella: un contatto si iscrive (o entra in waitlist).",
    )
    brevo_connection_event_cancelled_template_id: int = Field(
        default=0,
        validation_alias="BREVO_CONNECTION_EVENT_CANCELLED_TEMPLATE_ID",
        description="Template Brevo per la campanella: un contatto annulla l'iscrizione.",
    )
    brevo_crm_list_ids: str = Field(
        default="",
        validation_alias="BREVO_CRM_LIST_IDS",
        description="ID liste Brevo (virgola) per i contatti CRM; vuoto = tutti i contatti account.",
    )

    # MEDIA / OBJECT STORAGE
    public_api_url: str = Field(
        default="http://127.0.0.1:8000",
        validation_alias="PUBLIC_API_URL",
        description="URL pubblico di tn-be (QR email e GET /media/... per avatar/cover).",
    )
    storage_backend: Literal["local", "s3"] = Field(
        default="local",
        validation_alias="STORAGE_BACKEND",
        description="local = disco; s3 = Railway Bucket (file serviti da GET /media, bucket privato).",
    )
    storage_local_dir: str = Field(
        default="var/storage",
        validation_alias="STORAGE_LOCAL_DIR",
    )
    s3_endpoint_url: str = Field(default="", validation_alias="S3_ENDPOINT_URL")
    s3_region: str = Field(default="auto", validation_alias="S3_REGION")
    s3_bucket: str = Field(default="", validation_alias="S3_BUCKET")
    s3_access_key_id: str = Field(default="", validation_alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field(default="", validation_alias="S3_SECRET_ACCESS_KEY")
    s3_addressing_style: Literal["virtual", "path"] = Field(
        default="virtual",
        validation_alias="S3_ADDRESSING_STYLE",
        description="virtual = Railway Bucket nuovi; path = bucket vecchi (tab Credentials).",
    )

    @property
    def uses_redis_refresh_store(self) -> bool:
        """True se i refresh token sono gestiti su Redis."""
        return self.refresh_token_store.strip().lower() == "redis"

    @property
    def refresh_token_ttl_seconds(self) -> int:
        """TTL refresh session su Redis (allineato a JWT_REFRESH_TOKEN_EXPIRE_DAYS)."""
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

    @model_validator(mode="after")
    def strip_public_urls(self) -> Self:
        object.__setattr__(self, "public_api_url", self.public_api_url.strip().rstrip("/"))
        object.__setattr__(self, "s3_endpoint_url", self.s3_endpoint_url.strip().rstrip("/"))
        return self

    @model_validator(mode="after")
    def validate_s3_storage(self) -> Self:
        if self.storage_backend != "s3":
            return self
        missing: list[str] = []
        if not self.s3_bucket.strip():
            missing.append("S3_BUCKET")
        if not self.s3_access_key_id.strip():
            missing.append("S3_ACCESS_KEY_ID")
        if not self.s3_secret_access_key.strip():
            missing.append("S3_SECRET_ACCESS_KEY")
        if not self.s3_endpoint_url.strip():
            missing.append("S3_ENDPOINT_URL")
        if missing:
            raise ValueError(f"{', '.join(missing)} required when STORAGE_BACKEND=s3")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
