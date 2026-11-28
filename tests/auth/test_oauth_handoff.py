import uuid
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from auth.schemas.login import AuthUserBrief, TokenResponse
from auth.utils.oauth import OAuthSignInResult, build_frontend_redirect_url
from auth.utils.oauth_handoff import consume_oauth_handoff


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def getdel(self, key: str) -> str | None:
        return self.store.pop(key, None)


async def test_oauth_redirect_keeps_tokens_out_of_the_url(monkeypatch) -> None:
    fake = _FakeRedis()
    monkeypatch.setattr(
        "auth.utils.oauth_handoff.get_async_redis_service",
        lambda: SimpleNamespace(get_client=lambda: fake),
    )
    result = OAuthSignInResult(
        oauth_status="existing_user",
        token_response=TokenResponse(
            access_token="access-secret",
            refresh_token="refresh-secret-value",
            expires_in=900,
            user=AuthUserBrief(
                id=uuid.uuid4(),
                email="ada@example.com",
                username="ada",
                status="active",
            ),
        ),
    )

    url = await build_frontend_redirect_url(
        "http://localhost:3000/auth/google/callback?next=/home",
        result,
    )
    parts = urlsplit(url)

    assert parts.query == "next=/home"
    assert "access-secret" not in url
    assert "refresh-secret-value" not in url
    assert "ada@example.com" not in url
    code = parse_qs(parts.fragment)["handoff"][0]

    payload = await consume_oauth_handoff(code)
    assert payload is not None
    assert payload["access_token"] == "access-secret"
    assert payload["refresh_token"] == "refresh-secret-value"
    assert payload["oauth_status"] == "existing_user"
    assert await consume_oauth_handoff(code) is None