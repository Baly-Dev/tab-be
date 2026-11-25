"""Helpers for CLI scripts that connect to Postgres (local, Railway, overrides)."""

from __future__ import annotations

import os
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

_RAILWAY_INTERNAL = ".railway.internal"
_RAILWAY_PUBLIC_HOST_MARKERS = (".proxy.rlwy.net", ".railway.app", "rlwy.net")


def redact_database_url(url: str) -> str:
    """Return ``url`` with the password replaced by ``***`` (safe to print)."""
    parsed = urlparse(url)
    if not parsed.password:
        return url
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    user = parsed.username or ""
    netloc = f"{user}:***@{host}{port}"
    return urlunparse(parsed._replace(netloc=netloc))


def database_host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def is_railway_internal_url(url: str) -> bool:
    host = database_host(url)
    return host.endswith(_RAILWAY_INTERNAL) or host == "railway.internal"


def is_railway_public_url(url: str) -> bool:
    host = database_host(url)
    return any(marker in host for marker in _RAILWAY_PUBLIC_HOST_MARKERS)


def is_railway_url(url: str) -> bool:
    host = database_host(url)
    return is_railway_internal_url(url) or is_railway_public_url(url) or "railway" in host


def with_sslmode_require(url: str) -> str:
    """Add ``sslmode=require`` when missing (Railway public TCP proxy)."""
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if query.get("sslmode"):
        return url
    query["sslmode"] = "require"
    return urlunparse(parsed._replace(query=urlencode(query)))


def prepare_connect_url(url: str) -> str:
    """Normalize a CLI URL: SSL on Railway public TCP proxy."""
    raw = url.strip()
    if not raw:
        return raw
    if is_railway_public_url(raw):
        return with_sslmode_require(raw)
    return raw


def parse_tcp_proxy(value: str) -> tuple[str, str]:
    """Parse ``host:port`` from ``railway tcp-proxy list`` (e.g. ``altaria.proxy.rlwy.net:30873``)."""
    raw = value.strip()
    host, sep, port = raw.rpartition(":")
    if not sep or not host or not port.isdigit():
        raise SystemExit(f"Invalid --tcp-proxy {value!r}, expected host:port")
    return host, port


def rewrite_url_authority(url: str, host: str, port: str | int) -> str:
    """Keep user/password/path/query; replace host and port (Railway TCP proxy)."""
    parsed = urlparse(url)
    username = parsed.username or ""
    password = parsed.password
    if username or password is not None:
        userinfo = quote(username, safe="")
        if password is not None:
            userinfo = f"{userinfo}:{quote(password, safe='')}"
        netloc = f"{userinfo}@{host}:{port}"
    else:
        netloc = f"{host}:{port}"
    return urlunparse(parsed._replace(netloc=netloc))


def apply_cli_database_url(
    *,
    explicit: str | None = None,
    prefer_public: bool = False,
    tcp_proxy: str | None = None,
) -> str | None:
    """Set ``DATABASE_URL`` from ``--database-url`` / ``--tcp-proxy`` / ``--public``.

    Returns the URL written to the environment, or ``None`` if unchanged.
    ``--tcp-proxy`` rewrites the injected internal ``DATABASE_URL`` (Railway
    often has a TCP proxy without ``DATABASE_PUBLIC_URL``).
    """
    if explicit and explicit.strip():
        base = explicit.strip()
    else:
        base = (os.environ.get("DATABASE_URL") or "").strip()

    if tcp_proxy and tcp_proxy.strip():
        if not base:
            raise SystemExit("DATABASE_URL is not set; cannot apply --tcp-proxy")
        host, port = parse_tcp_proxy(tcp_proxy)
        url = prepare_connect_url(rewrite_url_authority(base, host, port))
        os.environ["DATABASE_URL"] = url
        return url

    if explicit and explicit.strip():
        url = prepare_connect_url(explicit.strip())
        os.environ["DATABASE_URL"] = url
        return url

    public = (os.environ.get("DATABASE_PUBLIC_URL") or "").strip()
    if prefer_public:
        if public:
            url = prepare_connect_url(public)
            os.environ["DATABASE_URL"] = url
            return url
        if base and is_railway_public_url(base):
            url = prepare_connect_url(base)
            os.environ["DATABASE_URL"] = url
            return url
        raise SystemExit(
            "DATABASE_PUBLIC_URL is not set. Pass --tcp-proxy host:port "
            "(from `railway tcp-proxy list --service Postgres`)."
        )
    return None
