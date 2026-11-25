"""OAuth: state JWT, user resolution, frontend redirect, HTTP error mapping."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlencode, urlparse

import jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.errors.oauth_errors import (
    OAuthAccountError,
    OAuthExchangeError,
    OAuthNotConfiguredError,
    OAuthProfileError,
    OAuthSignInError,
    OAuthStateError,
)
from auth.models.social_account import AuthSocialAccount
from auth.models.user import AuthUser
from auth.schemas.login import TokenResponse
from auth.utils.registration import is_registration_complete
from auth.utils.roles import ensure_member_role
from auth.utils.session import build_token_response
from auth.utils.tokens import _require_secret
from auth.utils.username import generate_unique_username
from config import OAuthProvider, UserStatus

OAUTH_STATUS_NEW: Literal["new_user"] = "new_user"
OAUTH_STATUS_EXISTING: Literal["existing_user"] = "existing_user"


@dataclass(frozen=True)
class SocialUserProfile:
    """Normalized profile from an OIDC/OAuth provider."""

    sub: str
    email: str
    email_verified: bool
    given_name: str
    family_name: str
    picture: str | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class OAuthAuthorizePayload:
    authorization_url: str
    state: str


@dataclass(frozen=True)
class OAuthSignInResult:
    token_response: TokenResponse
    oauth_status: Literal["new_user", "existing_user"]


def oauth_state_jti() -> str:
    return uuid.uuid4().hex


def create_oauth_state(
    *,
    token_typ: str,
    expire_minutes: int,
    subject: str | None = None,
) -> str:
    """Signed anti-CSRF JWT. ``subject`` is the user id for Settings link flows."""
    _require_secret()
    now = datetime.now(tz=UTC)
    exp = now + timedelta(minutes=expire_minutes)
    payload: dict[str, Any] = {
        "typ": token_typ,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": oauth_state_jti(),
    }
    if subject:
        payload["sub"] = subject
    return jwt.encode(payload, _require_secret(), algorithm="HS256")


def decode_oauth_state(state: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            state.strip(),
            _require_secret(),
            algorithms=["HS256"],
            options={"require": ["exp", "typ"]},
        )
    except jwt.PyJWTError as exc:
        raise OAuthStateError("Invalid or expired OAuth state") from exc
    if not isinstance(payload, dict):
        raise OAuthStateError("Invalid OAuth state")
    return payload


def verify_oauth_state(*, token_typ: str, state: str) -> dict[str, Any]:
    payload = decode_oauth_state(state)
    if payload.get("typ") != token_typ:
        raise OAuthStateError("Invalid OAuth state type")
    return payload


def oauth_state_subject(payload: dict[str, Any]) -> uuid.UUID:
    raw = payload.get("sub")
    if not raw or not isinstance(raw, str):
        raise OAuthStateError("Invalid OAuth state subject")
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise OAuthStateError("Invalid OAuth state subject") from exc


def build_frontend_connected_accounts_url(
    frontend_callback_url: str,
    *,
    provider: str,
    error: str | None = None,
) -> str:
    parsed = urlparse(frontend_callback_url.strip())
    if parsed.scheme and parsed.netloc:
        origin = f"{parsed.scheme}://{parsed.netloc}"
    else:
        origin = frontend_callback_url.strip().rstrip("/")
    params = {"provider": provider}
    if error:
        params["error"] = error
    else:
        params["linked"] = provider
    return f"{origin}/settings/profile/connected-accounts?{urlencode(params)}"


def oauth_link_error_code(exc: OAuthSignInError) -> str:
    if isinstance(exc, OAuthNotConfiguredError):
        return "oauth_not_configured"
    if isinstance(exc, OAuthStateError):
        return "invalid_oauth_state"
    if isinstance(exc, OAuthAccountError):
        return "oauth_account_error"
    if isinstance(exc, OAuthExchangeError):
        return "oauth_exchange_failed"
    if isinstance(exc, OAuthProfileError):
        return "oauth_profile_error"
    return "link_failed"


def build_frontend_redirect_url(
    frontend_base: str,
    result: OAuthSignInResult,
) -> str:
    base = frontend_base.strip()
    tr = result.token_response
    params = {
        "access_token": tr.access_token,
        "refresh_token": tr.refresh_token,
        "token_type": tr.token_type,
        "expires_in": str(tr.expires_in),
        "oauth_status": result.oauth_status,
        "user_id": str(tr.user.id),
        "email": tr.user.email,
        "username": tr.user.username,
        "status": tr.user.status,
    }
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}{urlencode(params)}"


def complete_social_sign_in(
    db: Session,
    *,
    provider: OAuthProvider,
    profile: SocialUserProfile,
    provider_label: str,
) -> OAuthSignInResult:
    user, oauth_status = resolve_user_from_social_profile(db, provider, profile, provider_label)
    assert_user_can_sign_in(user, db=db)
    try:
        token_response = build_token_response(db, user)
    except ValueError as exc:
        db.rollback()
        raise OAuthNotConfiguredError("Auth is not configured") from exc
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise OAuthAccountError(f"Could not complete {provider_label} sign-in") from exc
    return OAuthSignInResult(token_response=token_response, oauth_status=oauth_status)


def resolve_user_from_social_profile(
    db: Session,
    provider: OAuthProvider,
    profile: SocialUserProfile,
    provider_label: str,
) -> tuple[AuthUser, Literal["new_user", "existing_user"]]:
    social = db.scalar(
        select(AuthSocialAccount).where(
            AuthSocialAccount.provider == provider,
            AuthSocialAccount.provider_user_id == profile.sub,
        )
    )
    if social is not None:
        user = db.get(AuthUser, social.user_id)
        if user is None or user.status == UserStatus.DELETED:
            db.delete(social)
            db.flush()
        else:
            social.email = profile.email
            social.raw_profile = profile.raw
            db.add(social)
            mark_email_verified_if_needed(user, profile)
            db.add(user)
            return user, oauth_status_for_user(db, user)

    user_by_email = db.scalar(select(AuthUser).where(AuthUser.email == profile.email))
    if user_by_email is not None:
        if str(user_by_email.email).strip().lower() != profile.email:
            raise OAuthAccountError(f"Email mismatch for {provider_label} account")
        if user_by_email.status == UserStatus.DELETED:
            raise OAuthAccountError("Account deleted")
        existing_social = db.scalar(
            select(AuthSocialAccount).where(
                AuthSocialAccount.user_id == user_by_email.id,
                AuthSocialAccount.provider == provider,
            )
        )
        if existing_social is not None:
            raise OAuthAccountError(f"Another {provider_label} account is linked to this user")
        db.add(
            AuthSocialAccount(
                user_id=user_by_email.id,
                provider=provider,
                provider_user_id=profile.sub,
                email=profile.email,
                raw_profile=profile.raw,
            )
        )
        mark_email_verified_if_needed(user_by_email, profile)
        db.add(user_by_email)
        return user_by_email, oauth_status_for_user(db, user_by_email)

    given, family = _names_from_profile(profile)
    user = AuthUser(
        email=profile.email,
        username=generate_unique_username(
            db,
            profile.email,
            first_name=given,
            last_name=family,
        ),
        first_name=given,
        last_name=family,
        password_hash=None,
        status=UserStatus.PENDING,
        email_verified_at=datetime.now(tz=UTC) if profile.email_verified else None,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        raise OAuthAccountError("Email or username already registered") from exc

    db.add(
        AuthSocialAccount(
            user_id=user.id,
            provider=provider,
            provider_user_id=profile.sub,
            email=profile.email,
            raw_profile=profile.raw,
        )
    )
    ensure_member_role(db, user.id)
    return user, OAUTH_STATUS_NEW


def mark_email_verified_if_needed(user: AuthUser, profile: SocialUserProfile) -> None:
    """Mark the email verified by the provider. ACTIVE still requires POST /signup."""
    if profile.email_verified and user.email_verified_at is None:
        user.email_verified_at = datetime.now(tz=UTC)


def oauth_status_for_user(db: Session, user: AuthUser) -> Literal["new_user", "existing_user"]:
    if user.status == UserStatus.ACTIVE and is_registration_complete(db, user.id):
        return OAUTH_STATUS_EXISTING
    return OAUTH_STATUS_NEW


def assert_user_can_sign_in(user: AuthUser, *, db: Session) -> None:
    if user.status == UserStatus.SUSPENDED:
        raise OAuthAccountError("Account suspended")
    if user.status == UserStatus.DELETED:
        raise OAuthAccountError("Account deleted")
    if user.status == UserStatus.ACTIVE:
        return
    if user.status == UserStatus.PENDING:
        if is_registration_complete(db, user.id):
            raise OAuthAccountError("Account is not active")
        return
    raise OAuthAccountError("Account is not active")


def split_full_name(name: str) -> tuple[str, str]:
    parts = name.strip().split(None, 1)
    if not parts:
        return "User", "User"
    if len(parts) == 1:
        return parts[0], "User"
    return parts[0], parts[1]


def _names_from_profile(profile: SocialUserProfile) -> tuple[str, str]:
    given = profile.given_name.strip()
    family = profile.family_name.strip()
    if given and family:
        return given, family
    if given:
        return split_full_name(given)
    if family:
        return split_full_name(family)
    return "User", "User"


def complete_social_link(
    db: Session,
    *,
    user_id: uuid.UUID,
    provider: OAuthProvider,
    profile: SocialUserProfile,
    provider_label: str,
) -> None:
    user = db.get(AuthUser, user_id)
    if user is None or user.status in (UserStatus.DELETED, UserStatus.SUSPENDED):
        raise OAuthAccountError("Account cannot link OAuth")
    if user.status != UserStatus.ACTIVE:
        raise OAuthAccountError("Account is not active")

    user_email = str(user.email).strip().lower()
    if user_email != profile.email.strip().lower():
        raise OAuthAccountError(f"Email mismatch for {provider_label} account")

    existing_for_user = db.scalar(
        select(AuthSocialAccount).where(
            AuthSocialAccount.user_id == user.id,
            AuthSocialAccount.provider == provider,
        )
    )
    if existing_for_user is not None:
        if existing_for_user.provider_user_id == profile.sub:
            existing_for_user.email = profile.email
            existing_for_user.raw_profile = profile.raw
            db.add(existing_for_user)
            mark_email_verified_if_needed(user, profile)
            db.add(user)
            _commit_social_link(db, provider_label)
            return
        raise OAuthAccountError(f"Another {provider_label} account is linked to this user")

    existing_remote = db.scalar(
        select(AuthSocialAccount).where(
            AuthSocialAccount.provider == provider,
            AuthSocialAccount.provider_user_id == profile.sub,
        )
    )
    if existing_remote is not None:
        raise OAuthAccountError(f"This {provider_label} account is already linked to another user")

    db.add(
        AuthSocialAccount(
            user_id=user.id,
            provider=provider,
            provider_user_id=profile.sub,
            email=profile.email,
            raw_profile=profile.raw,
        )
    )
    mark_email_verified_if_needed(user, profile)
    db.add(user)
    _commit_social_link(db, provider_label)


def _commit_social_link(db: Session, provider_label: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise OAuthAccountError(f"Could not link {provider_label} account") from exc
