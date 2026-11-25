"""Sentry SDK bootstrap for the FastAPI app and background jobs.

Init must run before ``FastAPI()`` is constructed so the FastAPI/Starlette
integrations wrap the app. If ``SENTRY_DSN`` is empty the SDK stays disabled.
"""

from __future__ import annotations

import logging
import re
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import sentry_sdk
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

_DROP_TRACE_PATHS = frozenset(
    {
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    }
)

_DEFAULT_TRACES_SAMPLE_RATE: dict[str, float] = {
    "local": 1.0,
    "development": 1.0,
    "staging": 0.5,
    "production": 0.1,
}

_DEFAULT_PROFILE_SESSION_SAMPLE_RATE: dict[str, float] = {
    "local": 1.0,
    "development": 1.0,
    "staging": 0.2,
    "production": 0.1,
}

_initialized = False

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_SENSITIVE_QUERY_RE = re.compile(
    r"([?&])(access_token|refresh_token|id_token|token|code|email|password|reset|session)=[^&#\s]*",
    re.IGNORECASE,
)
_SENSITIVE_HEADERS = frozenset(
    {"authorization", "cookie", "set-cookie", "x-forwarded-for", "x-real-ip"}
)


def _redact_text(value: str) -> str:
    return _SENSITIVE_QUERY_RE.sub(r"\1\2=[redacted]", _EMAIL_RE.sub("[redacted]", value))


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_value(item) for key, item in value.items()}
    return value


def scrub_sentry_event(
    event: dict[str, Any],
    _hint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Drop emails, tokens, IPs and request bodies before the event is sent."""
    user = event.get("user")
    if isinstance(user, dict):
        for key in ("email", "ip_address", "username", "name"):
            user.pop(key, None)

    request = event.get("request")
    if isinstance(request, dict):
        request.pop("cookies", None)
        request.pop("data", None)
        request.pop("query_string", None)
        url = request.get("url")
        if isinstance(url, str):
            request["url"] = _redact_text(url)
        headers = request.get("headers")
        if isinstance(headers, dict):
            for key in list(headers):
                if str(key).lower() in _SENSITIVE_HEADERS:
                    headers.pop(key, None)

    message = event.get("message")
    if isinstance(message, str):
        event["message"] = _redact_text(message)

    breadcrumbs = event.get("breadcrumbs")
    crumb_values = breadcrumbs.get("values") if isinstance(breadcrumbs, dict) else breadcrumbs
    if isinstance(crumb_values, list):
        for crumb in crumb_values:
            if not isinstance(crumb, dict):
                continue
            crumb_message = crumb.get("message")
            if isinstance(crumb_message, str):
                crumb["message"] = _redact_text(crumb_message)
            if "data" in crumb:
                crumb["data"] = _redact_value(crumb.get("data"))

    exception = event.get("exception")
    values = exception.get("values") if isinstance(exception, dict) else None
    if isinstance(values, list):
        for item in values:
            if isinstance(item, dict) and isinstance(item.get("value"), str):
                item["value"] = _redact_text(item["value"])

    if "extra" in event:
        event["extra"] = _redact_value(event.get("extra"))

    return event


def scrub_sentry_log(log: dict[str, Any], _hint: dict[str, Any] | None = None) -> dict[str, Any]:
    """Redact emails and tokens inside log lines forwarded to Sentry."""
    body = log.get("body")
    if isinstance(body, str):
        log["body"] = _redact_text(body)
    attributes = log.get("attributes")
    if attributes is not None:
        log["attributes"] = _redact_value(attributes)
    return log


def _package_release() -> str:
    try:
        return f"tn-be@{version('tn-be')}"
    except PackageNotFoundError:
        return "tn-be@0.1.0"


def _traces_sample_rate(settings: Settings) -> float:
    if settings.sentry_traces_sample_rate is not None:
        return max(0.0, min(1.0, settings.sentry_traces_sample_rate))
    return _DEFAULT_TRACES_SAMPLE_RATE.get(settings.app_env, 0.1)


def _profile_session_sample_rate(settings: Settings) -> float:
    if settings.sentry_profile_session_sample_rate is not None:
        return max(0.0, min(1.0, settings.sentry_profile_session_sample_rate))
    return _DEFAULT_PROFILE_SESSION_SAMPLE_RATE.get(settings.app_env, 0.1)


def _path_from_sampling_context(sampling_context: dict[str, Any]) -> str:
    asgi_scope = sampling_context.get("asgi_scope") or {}
    path = asgi_scope.get("path")
    if isinstance(path, str) and path:
        return path
    transaction = sampling_context.get("transaction_context") or {}
    name = transaction.get("name")
    if isinstance(name, str):
        return name.rsplit(" ", 1)[-1]
    return ""


def _traces_sampler(sampling_context: dict[str, Any]) -> float:
    parent = sampling_context.get("parent_sampled")
    if parent is not None:
        return float(parent)
    path = _path_from_sampling_context(sampling_context)
    if path in _DROP_TRACE_PATHS:
        return 0.0
    return _traces_sample_rate(get_settings())


def _bind_user_from_bearer(authorization: str | None) -> None:
    if not authorization:
        return
    raw = authorization.strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()
    if not raw or raw.count(".") != 2:
        return
    try:
        from auth.utils.tokens import decode_access_token

        payload = decode_access_token(raw)
    except Exception:
        return
    user_id = payload.get("sub")
    if not user_id:
        return
    sentry_sdk.set_user({"id": str(user_id)})
    roles = payload.get("roles")
    if isinstance(roles, list) and roles:
        sentry_sdk.set_tag("user.roles", ",".join(str(role) for role in roles))


class SentryUserMiddleware:
    """Attach authenticated user id/email to the current Sentry scope."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and sentry_sdk.is_initialized():
            request = Request(scope)
            _bind_user_from_bearer(
                request.headers.get("authorization") or request.headers.get("Authorization")
            )
        await self.app(scope, receive, send)


def init_sentry(*, component: str = "api") -> bool:
    """Initialize the Sentry SDK. Returns True if a DSN was configured."""
    global _initialized
    if _initialized:
        return sentry_sdk.is_initialized()

    settings = get_settings()
    dsn = settings.sentry_dsn.strip()
    if not dsn:
        logger.info("Sentry disabled (SENTRY_DSN empty)")
        _initialized = True
        return False

    environment = settings.sentry_environment.strip() or settings.app_env
    release = settings.sentry_release.strip() or _package_release()

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        send_default_pii=False,
        before_send=scrub_sentry_event,
        before_send_transaction=scrub_sentry_event,
        before_send_log=scrub_sentry_log,
        traces_sampler=_traces_sampler,
        profile_session_sample_rate=_profile_session_sample_rate(settings),
        profile_lifecycle="trace",
        enable_logs=True,
        in_app_include=["auth", "admin", "core", "events", "notifications", "config", "services"],
    )
    sentry_sdk.set_tag("component", component)
    _initialized = True
    logger.info(
        "Sentry initialized environment=%s release=%s component=%s",
        environment,
        release,
        component,
    )
    return True
