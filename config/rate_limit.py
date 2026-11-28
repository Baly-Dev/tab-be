"""Rate-limit knobs and the structured policy used by auth and the API middleware.

Every window is an env var on ``Settings`` (``RATE_LIMIT_*``). ``0`` max_attempts
disables that bucket. Code must read ``settings.rate_limit``, not literals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self

from pydantic import AliasChoices, BaseModel, Field, field_validator

_STAGING_OR_PROD = frozenset({"staging", "production"})


@dataclass(frozen=True, slots=True)
class RateLimitWindow:
    """Fixed window: at most ``max_attempts`` hits in ``window_seconds``."""

    max_attempts: int
    window_seconds: int

    @property
    def disabled(self) -> bool:
        return self.max_attempts <= 0 or self.window_seconds <= 0


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    """Resolved rate-limit policy. Built from ``Settings``, never from literals."""

    enabled: bool
    fail_closed: bool
    trust_x_forwarded_for: bool
    redis_prefix: str
    login_lockout_seconds: int
    login_ip: RateLimitWindow
    login_identifier: RateLimitWindow
    signup_ip: RateLimitWindow
    signup_email: RateLimitWindow
    password_reset_ip: RateLimitWindow
    password_reset_email: RateLimitWindow
    verify_email_ip: RateLimitWindow
    resend_verification_ip: RateLimitWindow
    resend_verification_email: RateLimitWindow
    oauth_ip: RateLimitWindow
    passkey_ip: RateLimitWindow
    oauth_handoff_ip: RateLimitWindow
    refresh_ip: RateLimitWindow
    api_ip: RateLimitWindow

    @classmethod
    def from_settings(cls, settings: Any) -> Self:
        fail_closed = settings.rate_limit_fail_closed
        if fail_closed is None:
            fail_closed = settings.app_env in _STAGING_OR_PROD
        prefix = str(settings.rate_limit_redis_prefix or "tn:rl").strip() or "tn:rl"
        return cls(
            enabled=bool(settings.rate_limit_enabled),
            fail_closed=bool(fail_closed),
            trust_x_forwarded_for=bool(settings.rate_limit_trust_x_forwarded_for),
            redis_prefix=prefix.rstrip(":"),
            login_lockout_seconds=max(0, int(settings.rate_limit_login_lockout_seconds)),
            login_ip=_window(
                settings.rate_limit_login_ip_max_attempts,
                settings.rate_limit_login_ip_window_seconds,
            ),
            login_identifier=_window(
                settings.rate_limit_login_identifier_max_attempts,
                settings.rate_limit_login_identifier_window_seconds,
            ),
            signup_ip=_window(
                settings.rate_limit_signup_ip_max_attempts,
                settings.rate_limit_signup_ip_window_seconds,
            ),
            signup_email=_window(
                settings.rate_limit_signup_email_max_attempts,
                settings.rate_limit_signup_email_window_seconds,
            ),
            password_reset_ip=_window(
                settings.rate_limit_password_reset_ip_max_attempts,
                settings.rate_limit_password_reset_ip_window_seconds,
            ),
            password_reset_email=_window(
                settings.rate_limit_password_reset_email_max_attempts,
                settings.rate_limit_password_reset_email_window_seconds,
            ),
            verify_email_ip=_window(
                settings.rate_limit_verify_email_ip_max_attempts,
                settings.rate_limit_verify_email_ip_window_seconds,
            ),
            resend_verification_ip=_window(
                settings.rate_limit_resend_verification_ip_max_attempts,
                settings.rate_limit_resend_verification_ip_window_seconds,
            ),
            resend_verification_email=_window(
                settings.rate_limit_resend_verification_email_max_attempts,
                settings.rate_limit_resend_verification_email_window_seconds,
            ),
            oauth_ip=_window(
                settings.rate_limit_oauth_ip_max_attempts,
                settings.rate_limit_oauth_ip_window_seconds,
            ),
            passkey_ip=_window(
                settings.rate_limit_passkey_ip_max_attempts,
                settings.rate_limit_passkey_ip_window_seconds,
            ),
            oauth_handoff_ip=_window(
                settings.rate_limit_oauth_handoff_ip_max_attempts,
                settings.rate_limit_oauth_handoff_ip_window_seconds,
            ),
            refresh_ip=_window(
                settings.rate_limit_refresh_ip_max_attempts,
                settings.rate_limit_refresh_ip_window_seconds,
            ),
            api_ip=_window(
                settings.rate_limit_api_ip_max_attempts,
                settings.rate_limit_api_ip_window_seconds,
            ),
        )


def _window(max_attempts: int, window_seconds: int) -> RateLimitWindow:
    return RateLimitWindow(max_attempts=int(max_attempts), window_seconds=int(window_seconds))


class RateLimitEnvMixin(BaseModel):
    """``RATE_LIMIT_*`` env vars. Inherited by ``Settings`` so they live next to JWT and Redis."""

    rate_limit_enabled: bool = Field(default=True, validation_alias="RATE_LIMIT_ENABLED")
    rate_limit_fail_closed: bool | None = Field(
        default=None,
        validation_alias="RATE_LIMIT_FAIL_CLOSED",
        description="If Redis is down: refuse requests (true) or skip limits (false). "
        "Unset = true in staging/production, false otherwise.",
    )
    rate_limit_trust_x_forwarded_for: bool = Field(
        default=False,
        validation_alias="RATE_LIMIT_TRUST_X_FORWARDED_FOR",
        description="Read client IP from X-Forwarded-For / X-Real-IP. Enable behind Next or nginx.",
    )
    rate_limit_redis_prefix: str = Field(
        default="tn:rl",
        validation_alias="RATE_LIMIT_REDIS_PREFIX",
    )

    rate_limit_login_ip_max_attempts: int = Field(
        default=30,
        validation_alias="RATE_LIMIT_LOGIN_IP_MAX_ATTEMPTS",
    )
    rate_limit_login_ip_window_seconds: int = Field(
        default=900,
        validation_alias="RATE_LIMIT_LOGIN_IP_WINDOW_SECONDS",
    )
    rate_limit_login_identifier_max_attempts: int = Field(
        default=8,
        validation_alias="RATE_LIMIT_LOGIN_IDENTIFIER_MAX_ATTEMPTS",
    )
    rate_limit_login_identifier_window_seconds: int = Field(
        default=900,
        validation_alias="RATE_LIMIT_LOGIN_IDENTIFIER_WINDOW_SECONDS",
    )
    rate_limit_login_lockout_seconds: int = Field(
        default=900,
        validation_alias="RATE_LIMIT_LOGIN_LOCKOUT_SECONDS",
        description="Extra freeze on an identifier after it hits max attempts. 0 = window only.",
    )

    rate_limit_signup_ip_max_attempts: int = Field(
        default=10,
        validation_alias="RATE_LIMIT_SIGNUP_IP_MAX_ATTEMPTS",
    )
    rate_limit_signup_ip_window_seconds: int = Field(
        default=3600,
        validation_alias="RATE_LIMIT_SIGNUP_IP_WINDOW_SECONDS",
    )
    rate_limit_signup_email_max_attempts: int = Field(
        default=5,
        validation_alias="RATE_LIMIT_SIGNUP_EMAIL_MAX_ATTEMPTS",
    )
    rate_limit_signup_email_window_seconds: int = Field(
        default=3600,
        validation_alias="RATE_LIMIT_SIGNUP_EMAIL_WINDOW_SECONDS",
    )

    rate_limit_password_reset_ip_max_attempts: int = Field(
        default=10,
        validation_alias="RATE_LIMIT_PASSWORD_RESET_IP_MAX_ATTEMPTS",
    )
    rate_limit_password_reset_ip_window_seconds: int = Field(
        default=3600,
        validation_alias="RATE_LIMIT_PASSWORD_RESET_IP_WINDOW_SECONDS",
    )
    rate_limit_password_reset_email_max_attempts: int = Field(
        default=5,
        validation_alias=AliasChoices(
            "RATE_LIMIT_PASSWORD_RESET_EMAIL_MAX_ATTEMPTS",
            "PASSWORD_RESET_RATE_LIMIT_PER_HOUR",
        ),
        description="Per-email forgot-password cap. Legacy: PASSWORD_RESET_RATE_LIMIT_PER_HOUR.",
    )
    rate_limit_password_reset_email_window_seconds: int = Field(
        default=3600,
        validation_alias="RATE_LIMIT_PASSWORD_RESET_EMAIL_WINDOW_SECONDS",
    )

    rate_limit_verify_email_ip_max_attempts: int = Field(
        default=20,
        validation_alias="RATE_LIMIT_VERIFY_EMAIL_IP_MAX_ATTEMPTS",
    )
    rate_limit_verify_email_ip_window_seconds: int = Field(
        default=3600,
        validation_alias="RATE_LIMIT_VERIFY_EMAIL_IP_WINDOW_SECONDS",
    )
    rate_limit_resend_verification_ip_max_attempts: int = Field(
        default=10,
        validation_alias="RATE_LIMIT_RESEND_VERIFICATION_IP_MAX_ATTEMPTS",
    )
    rate_limit_resend_verification_ip_window_seconds: int = Field(
        default=3600,
        validation_alias="RATE_LIMIT_RESEND_VERIFICATION_IP_WINDOW_SECONDS",
    )
    rate_limit_resend_verification_email_max_attempts: int = Field(
        default=3,
        validation_alias="RATE_LIMIT_RESEND_VERIFICATION_EMAIL_MAX_ATTEMPTS",
    )
    rate_limit_resend_verification_email_window_seconds: int = Field(
        default=3600,
        validation_alias="RATE_LIMIT_RESEND_VERIFICATION_EMAIL_WINDOW_SECONDS",
    )

    rate_limit_oauth_ip_max_attempts: int = Field(
        default=20,
        validation_alias="RATE_LIMIT_OAUTH_IP_MAX_ATTEMPTS",
    )
    rate_limit_oauth_ip_window_seconds: int = Field(
        default=900,
        validation_alias="RATE_LIMIT_OAUTH_IP_WINDOW_SECONDS",
    )
    rate_limit_passkey_ip_max_attempts: int = Field(
        default=20,
        validation_alias="RATE_LIMIT_PASSKEY_IP_MAX_ATTEMPTS",
    )
    rate_limit_passkey_ip_window_seconds: int = Field(
        default=900,
        validation_alias="RATE_LIMIT_PASSKEY_IP_WINDOW_SECONDS",
    )
    rate_limit_oauth_handoff_ip_max_attempts: int = Field(
        default=30,
        validation_alias="RATE_LIMIT_OAUTH_HANDOFF_IP_MAX_ATTEMPTS",
    )
    rate_limit_oauth_handoff_ip_window_seconds: int = Field(
        default=300,
        validation_alias="RATE_LIMIT_OAUTH_HANDOFF_IP_WINDOW_SECONDS",
    )
    rate_limit_refresh_ip_max_attempts: int = Field(
        default=60,
        validation_alias="RATE_LIMIT_REFRESH_IP_MAX_ATTEMPTS",
    )
    rate_limit_refresh_ip_window_seconds: int = Field(
        default=60,
        validation_alias="RATE_LIMIT_REFRESH_IP_WINDOW_SECONDS",
    )
    rate_limit_api_ip_max_attempts: int = Field(
        default=300,
        validation_alias="RATE_LIMIT_API_IP_MAX_ATTEMPTS",
    )
    rate_limit_api_ip_window_seconds: int = Field(
        default=60,
        validation_alias="RATE_LIMIT_API_IP_WINDOW_SECONDS",
    )

    @field_validator("rate_limit_fail_closed", mode="before")
    @classmethod
    def empty_fail_closed_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @property
    def rate_limit(self) -> RateLimitPolicy:
        return RateLimitPolicy.from_settings(self)