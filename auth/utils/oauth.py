"""OAuth social: state JWT, risoluzione utente, redirect FE e mapping errori HTTP."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlencode, urlparse

import jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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
from auth.utils.oauth_handoff import handoff_redirect_url, issue_oauth_handoff
from auth.utils.registration import is_registration_complete
from auth.utils.session import build_token_response
from auth.utils.tokens import _require_secret
from auth.utils.username import generate_unique_username
from config import AppRole, OAuthProvider, UserStatus
from core.models.profile import CoreProfile
from core.models.user_role import CoreUserRole
from core.services.provider_avatar import apply_provider_avatar

OAUTH_STATUS_NEW: Literal["new_user"] = "new_user"
OAUTH_STATUS_EXISTING: Literal["existing_user"] = "existing_user"


@dataclass(frozen=True)
class SocialUserProfile:
    """Profilo normalizzato da un provider OIDC/OAuth."""

    sub: str
    email: str
    email_verified: bool
    given_name: str
    family_name: str
    picture: str | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class OAuthAuthorizePayload:
    """URL verso il provider e state CSRF."""

    authorization_url: str
    state: str


@dataclass(frozen=True)
class OAuthSignInResult:
    """Token Trustnet + flag nuovo/utente esistente."""

    token_response: TokenResponse
    oauth_status: Literal["new_user", "existing_user"]


def oauth_state_jti() -> str:
    """JTI univoco per state OAuth."""
    return uuid.uuid4().hex


def create_oauth_state(
    *,
    token_typ: str,
    expire_minutes: int,
    subject: str | None = None,
) -> str:
    """JWT firmato anti-CSRF con ``typ`` dedicato al provider.

    ``subject`` (user id) è usato per i flussi di link da Settings.
    """
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
    """Decodifica e valida firma/scadenza dello state OAuth (senza vincolare ``typ``)."""
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
    """Valida state JWT; solleva ``OAuthStateError`` se invalido."""
    payload = decode_oauth_state(state)
    if payload.get("typ") != token_typ:
        raise OAuthStateError("Invalid OAuth state type")
    return payload


def oauth_state_subject(payload: dict[str, Any]) -> uuid.UUID:
    """Estrae ``sub`` (user id) dallo state di link; solleva se assente o invalido."""
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
    """Redirect post-link verso Settings (senza token in query)."""
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
    """Codice query per redirect FE dopo link OAuth fallito."""
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


async def build_frontend_redirect_url(
    frontend_base: str,
    result: OAuthSignInResult,
) -> str:
    """Redirect al FE con un codice monouso nel fragment, non i token in query."""
    code = await issue_oauth_handoff(
        {
            "oauth_status": result.oauth_status,
            **result.token_response.model_dump(mode="json"),
        }
    )
    return handoff_redirect_url(frontend_base, code)


async def complete_social_sign_in(
    db: AsyncSession,
    *,
    provider: OAuthProvider,
    profile: SocialUserProfile,
    provider_label: str,
) -> OAuthSignInResult:
    """Collega/crea utente e emette token; commit transazione."""
    user, oauth_status = await resolve_user_from_social_profile(db, provider, profile, provider_label)
    await assert_user_can_sign_in(user, db=db)
    try:
        token_response = await build_token_response(db, user)
    except ValueError as exc:
        await db.rollback()
        raise OAuthNotConfiguredError("Auth is not configured") from exc
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise OAuthAccountError(f"Could not complete {provider_label} sign-in") from exc
    return OAuthSignInResult(token_response=token_response, oauth_status=oauth_status)


async def resolve_user_from_social_profile(
    db: AsyncSession,
    provider: OAuthProvider,
    profile: SocialUserProfile,
    provider_label: str,
) -> tuple[AuthUser, Literal["new_user", "existing_user"]]:
    """Trova o crea utente da ``auth_social_accounts`` / email / nuovo account."""
    social = await db.scalar(
        select(AuthSocialAccount).where(
            AuthSocialAccount.provider == provider,
            AuthSocialAccount.provider_user_id == profile.sub,
        )
    )
    if social is not None:
        user = await db.get(AuthUser, social.user_id)
        # Soft-delete senza unlink: rimuovi link stale e continua come nuovo signup OAuth
        if user is None or user.status == UserStatus.DELETED:
            await db.delete(social)
            await db.flush()
        else:
            social.sync_provider_profile(email=profile.email, raw_profile=profile.raw)
            db.add(social)
            user.mark_email_verified_from_provider(email_verified=profile.email_verified)
            await maybe_update_profile_avatar(db, user.id, profile)
            db.add(user)
            return user, await oauth_status_for_user(db, user)

    user_by_email = await db.scalar(select(AuthUser).where(AuthUser.email == profile.email))
    if user_by_email is not None:
        if str(user_by_email.email).strip().lower() != profile.email:
            raise OAuthAccountError(f"Email mismatch for {provider_label} account")
        # Soft-deleted senza anonymize: non riusare
        if user_by_email.status == UserStatus.DELETED:
            raise OAuthAccountError("Account deleted")
        existing_social = await db.scalar(
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
        user_by_email.mark_email_verified_from_provider(email_verified=profile.email_verified)
        await maybe_update_profile_avatar(db, user_by_email.id, profile)
        db.add(user_by_email)
        return user_by_email, await oauth_status_for_user(db, user_by_email)

    user = AuthUser(
        email=profile.email,
        username=await generate_unique_username(
            db, profile.email,
            first_name=profile.given_name,
            last_name=profile.family_name,
        ),
        password_hash=None,
        status=UserStatus.PENDING,
        email_verified_at=datetime.now(tz=UTC) if profile.email_verified else None,
    )
    db.add(user)
    try:
        await db.flush()
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
    db.add(
        CoreProfile(
            user_id=user.id,
            first_name=profile.given_name,
            last_name=profile.family_name,
            avatar_url=None,
        )
    )
    await db.flush()
    await maybe_update_profile_avatar(db, user.id, profile)
    db.add(CoreUserRole(user_id=user.id, role=AppRole.PROFESSIONAL))
    return user, OAUTH_STATUS_NEW


async def oauth_status_for_user(db: AsyncSession, user: AuthUser) -> Literal["new_user", "existing_user"]:
    """``existing_user`` se l'account è già operativo (ACTIVE con profilo)."""
    if user.status == UserStatus.ACTIVE and await is_registration_complete(db, user.id):
        return OAUTH_STATUS_EXISTING
    return OAUTH_STATUS_NEW


async def maybe_update_profile_avatar(
    db: AsyncSession,
    user_id: uuid.UUID,
    profile: SocialUserProfile,
) -> None:
    """Copia la foto del provider nel bucket se il profilo non ne ha già una nostra.

    Un fallimento del download non blocca il login: l'URL LinkedIn/Google non viene salvato.
    """
    if not profile.picture:
        return
    core_profile = await db.get(CoreProfile, user_id)
    if core_profile is None:
        core_profile = CoreProfile(
            user_id=user_id,
            first_name=profile.given_name,
            last_name=profile.family_name,
            avatar_url=None,
        )
        db.add(core_profile)
        await db.flush()
    await apply_provider_avatar(db, core_profile, profile.picture)


async def assert_user_can_sign_in(user: AuthUser, *, db: AsyncSession) -> None:
    """Blocca sospesi/eliminati; PENDING ammesso solo se wizard non completato."""
    if user.status == UserStatus.SUSPENDED:
        raise OAuthAccountError("Account suspended")
    if user.status == UserStatus.DELETED:
        raise OAuthAccountError("Account deleted")
    if user.status == UserStatus.ACTIVE:
        return
    if user.status == UserStatus.PENDING:
        if await is_registration_complete(db, user.id):
            raise OAuthAccountError("Account is not active")
        return
    raise OAuthAccountError("Account is not active")


def split_full_name(name: str) -> tuple[str, str]:
    """Suddivide nome completo in given/family (fallback User)."""
    parts = name.strip().split(None, 1)
    if not parts:
        return "User", "User"
    if len(parts) == 1:
        return parts[0], "User"
    return parts[0], parts[1]


async def complete_social_link(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider: OAuthProvider,
    profile: SocialUserProfile,
    provider_label: str,
) -> None:
    """Collega un account OAuth all'utente autenticato (flusso Settings)."""
    user = await db.get(AuthUser, user_id)
    if user is None or user.status in (UserStatus.DELETED, UserStatus.SUSPENDED):
        raise OAuthAccountError("Account cannot link OAuth")
    if user.status != UserStatus.ACTIVE:
        raise OAuthAccountError("Account is not active")

    user_email = str(user.email).strip().lower()
    if user_email != profile.email.strip().lower():
        raise OAuthAccountError(f"Email mismatch for {provider_label} account")

    existing_for_user = await db.scalar(
        select(AuthSocialAccount).where(
            AuthSocialAccount.user_id == user.id,
            AuthSocialAccount.provider == provider,
        )
    )
    if existing_for_user is not None:
        if existing_for_user.provider_user_id == profile.sub:
            existing_for_user.sync_provider_profile(email=profile.email, raw_profile=profile.raw)
            db.add(existing_for_user)
            user.mark_email_verified_from_provider(email_verified=profile.email_verified)
            await maybe_update_profile_avatar(db, user.id, profile)
            db.add(user)
            await _commit_social_link(db, provider_label)
            return
        raise OAuthAccountError(f"Another {provider_label} account is linked to this user")

    existing_remote = await db.scalar(
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
    user.mark_email_verified_from_provider(email_verified=profile.email_verified)
    await maybe_update_profile_avatar(db, user.id, profile)
    db.add(user)
    await _commit_social_link(db, provider_label)


async def _commit_social_link(db: AsyncSession, provider_label: str) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise OAuthAccountError(f"Could not link {provider_label} account") from exc
