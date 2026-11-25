"""WebAuthn / passkey: challenge JWT, options e verifica."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from auth.errors.passkey_errors import (
    http_error_invalid_passkey_challenge,
    http_error_passkey_registration_failed,
    http_error_webauthn_not_configured,
)
from auth.models.webauthn_credential import AuthWebAuthnCredential
from auth.utils.tokens import _require_secret
from config import get_settings

TOKEN_TYP_REGISTER = "webauthn_register"
TOKEN_TYP_AUTHENTICATE = "webauthn_authenticate"
ChallengePurpose = Literal["register", "authenticate"]

_PURPOSE_TYP = {
    "register": TOKEN_TYP_REGISTER,
    "authenticate": TOKEN_TYP_AUTHENTICATE,
}


def webauthn_is_configured() -> bool:
    settings = get_settings()
    return bool(settings.webauthn_rp_id.strip() and settings.webauthn_origin.strip())


def require_webauthn_config() -> None:
    if not webauthn_is_configured():
        raise http_error_webauthn_not_configured()
    try:
        _require_secret()
    except ValueError:
        raise http_error_webauthn_not_configured() from None


def _rp_id() -> str:
    return get_settings().webauthn_rp_id.strip()


def _rp_name() -> str:
    return get_settings().webauthn_rp_name.strip() or "Financ&youth"


def _expected_origin() -> str:
    return get_settings().webauthn_origin.strip().rstrip("/")


def options_as_dict(options: object) -> dict[str, Any]:
    raw = options_to_json(options)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise TypeError("WebAuthn options JSON must be an object")
    for key in ("allowCredentials", "excludeCredentials"):
        if not parsed.get(key):
            parsed.pop(key, None)
    return parsed


def create_challenge_token(
    *,
    purpose: ChallengePurpose,
    challenge: bytes,
    user_id: uuid.UUID | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(tz=UTC)
    exp = now + timedelta(minutes=settings.webauthn_challenge_expire_minutes)
    payload: dict[str, Any] = {
        "typ": _PURPOSE_TYP[purpose],
        "challenge": bytes_to_base64url(challenge),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": uuid.uuid4().hex,
    }
    if user_id is not None:
        payload["sub"] = str(user_id)
    return jwt.encode(payload, _require_secret(), algorithm="HS256")


def decode_challenge_token(token: str, *, purpose: ChallengePurpose) -> tuple[bytes, uuid.UUID | None]:
    try:
        payload = jwt.decode(
            token.strip(),
            _require_secret(),
            algorithms=["HS256"],
            options={"require": ["exp", "typ", "challenge"]},
        )
    except jwt.PyJWTError as exc:
        raise http_error_invalid_passkey_challenge() from exc
    if payload.get("typ") != _PURPOSE_TYP[purpose]:
        raise http_error_invalid_passkey_challenge()
    challenge_b64 = payload.get("challenge")
    if not isinstance(challenge_b64, str) or not challenge_b64:
        raise http_error_invalid_passkey_challenge()
    try:
        challenge = base64url_to_bytes(challenge_b64)
    except Exception as exc:
        raise http_error_invalid_passkey_challenge() from exc

    user_id: uuid.UUID | None = None
    sub = payload.get("sub")
    if isinstance(sub, str) and sub:
        try:
            user_id = uuid.UUID(sub)
        except ValueError as exc:
            raise http_error_invalid_passkey_challenge() from exc
    return challenge, user_id


def _transports_from_stored(values: list[str] | None) -> list[AuthenticatorTransport] | None:
    if not values:
        return None
    out: list[AuthenticatorTransport] = []
    for value in values:
        try:
            out.append(AuthenticatorTransport(value))
        except ValueError:
            continue
    return out or None


def descriptors_for(credentials: list[AuthWebAuthnCredential]) -> list[PublicKeyCredentialDescriptor]:
    return [
        PublicKeyCredentialDescriptor(
            id=bytes(row.credential_id),
            transports=_transports_from_stored(list(row.transports) if row.transports else None),
        )
        for row in credentials
    ]


def build_registration_options(
    *,
    user_id: uuid.UUID,
    user_name: str,
    display_name: str,
    existing: list[AuthWebAuthnCredential],
) -> tuple[dict[str, Any], str]:
    require_webauthn_config()
    options = generate_registration_options(
        rp_id=_rp_id(),
        rp_name=_rp_name(),
        user_id=user_id.bytes,
        user_name=user_name,
        user_display_name=display_name,
        exclude_credentials=descriptors_for(existing) or None,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        attestation=AttestationConveyancePreference.NONE,
        timeout=60_000,
    )
    token = create_challenge_token(purpose="register", challenge=options.challenge, user_id=user_id)
    return options_as_dict(options), token


def build_authentication_options(
    *,
    credentials: list[AuthWebAuthnCredential],
    user_id: uuid.UUID | None,
) -> tuple[dict[str, Any], str]:
    require_webauthn_config()
    options = generate_authentication_options(
        rp_id=_rp_id(),
        allow_credentials=descriptors_for(credentials) or None,
        user_verification=UserVerificationRequirement.REQUIRED,
        timeout=60_000,
    )
    token = create_challenge_token(
        purpose="authenticate",
        challenge=options.challenge,
        user_id=user_id,
    )
    return options_as_dict(options), token


def transports_from_credential(credential: dict[str, Any]) -> list[str] | None:
    raw = credential.get("transports")
    if raw is None:
        response = credential.get("response")
        if isinstance(response, dict):
            raw = response.get("transports")
    if not isinstance(raw, list):
        return None
    values = [str(item) for item in raw if isinstance(item, str)]
    return values or None


def credential_id_from_assertion(credential: dict[str, Any]) -> bytes:
    raw_id = credential.get("rawId") or credential.get("id")
    if not isinstance(raw_id, str) or not raw_id:
        raise http_error_invalid_passkey_challenge()
    try:
        return base64url_to_bytes(raw_id)
    except Exception as exc:
        raise http_error_invalid_passkey_challenge() from exc


def verify_registration(
    *,
    credential: dict[str, Any],
    challenge: bytes,
) -> Any:
    require_webauthn_config()
    try:
        return verify_registration_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=_rp_id(),
            expected_origin=_expected_origin(),
            require_user_verification=True,
        )
    except InvalidRegistrationResponse as exc:
        raise http_error_passkey_registration_failed() from exc


def verify_authentication(
    *,
    credential: dict[str, Any],
    challenge: bytes,
    public_key: bytes,
    sign_count: int,
) -> Any:
    require_webauthn_config()
    from auth.errors.login_errors import http_error_invalid_credentials

    try:
        return verify_authentication_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=_rp_id(),
            expected_origin=_expected_origin(),
            credential_public_key=public_key,
            credential_current_sign_count=sign_count,
            require_user_verification=True,
        )
    except InvalidAuthenticationResponse as exc:
        raise http_error_invalid_credentials() from exc
