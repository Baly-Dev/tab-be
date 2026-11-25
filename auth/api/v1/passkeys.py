"""Passkey / WebAuthn: registrazione autenticata e login passwordless."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.errors.login_errors import http_error_auth_not_configured, http_error_invalid_credentials
from auth.errors.passkey_errors import (
    http_error_cannot_delete_last_login,
    http_error_invalid_passkey_challenge,
    http_error_passkey_already_registered,
    http_error_passkey_not_found,
)
from auth.models.user import AuthUser
from auth.models.webauthn_credential import AuthWebAuthnCredential
from auth.schemas.login import TokenResponse, normalize_login_identifier
from auth.schemas.passkeys import (
    PasskeyAuthenticateOptionsRequest,
    PasskeyAuthenticateRequest,
    PasskeyDeleteResponse,
    PasskeyItem,
    PasskeyListResponse,
    PasskeyOptionsResponse,
    PasskeyRegisterRequest,
)
from auth.utils.account_status import raise_if_cannot_login
from auth.utils.helpers import AuthenticatedUser
from auth.utils.login_methods import count_login_methods
from auth.utils.session import build_token_response
from auth.utils.webauthn import (
    build_authentication_options,
    build_registration_options,
    credential_id_from_assertion,
    decode_challenge_token,
    transports_from_credential,
    verify_authentication,
    verify_registration,
)
from config.db.session import get_db
from core.models.profile import CoreProfile
from notifications.services.profile_incomplete import sync_profile_incomplete_notification

router = APIRouter(prefix="/passkeys")


def _device_label(raw: str | None) -> str:
    name = (raw or "").strip()
    return name[:80] if name else "Questo dispositivo"


def _display_name(db: Session, user: AuthUser) -> str:
    profile = db.get(CoreProfile, user.id)
    if profile is not None:
        full = f"{profile.first_name} {profile.last_name}".strip()
        if full:
            return full
    return str(user.email)


def _credentials_for_user(db: Session, user_id: uuid.UUID) -> list[AuthWebAuthnCredential]:
    return list(
        db.scalars(
            select(AuthWebAuthnCredential)
            .where(AuthWebAuthnCredential.user_id == user_id)
            .order_by(AuthWebAuthnCredential.created_at.desc())
        ).all()
    )


def _item(row: AuthWebAuthnCredential) -> PasskeyItem:
    return PasskeyItem(
        id=row.id,
        device_name=str(row.device_name),
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        backed_up=bool(row.backed_up),
    )


def _aaguid_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.hex()
    text = str(value).strip()
    return text or None


@router.post("/register/options", response_model=PasskeyOptionsResponse)
def register_options(user: AuthenticatedUser, db: Session = Depends(get_db)) -> PasskeyOptionsResponse:
    """Challenge per creare una passkey (Face ID / piattaforma) sull'account corrente."""
    options, challenge_token = build_registration_options(
        user_id=user.id,
        user_name=str(user.email),
        display_name=_display_name(db, user),
        existing=_credentials_for_user(db, user.id),
    )
    return PasskeyOptionsResponse(options=options, challenge_token=challenge_token)


@router.post("/register", response_model=PasskeyItem)
def register_passkey(
    body: PasskeyRegisterRequest,
    user: AuthenticatedUser,
    db: Session = Depends(get_db),
) -> PasskeyItem:
    """Verifica l'attestation e salva la credenziale."""
    challenge, token_user_id = decode_challenge_token(body.challenge_token, purpose="register")
    if token_user_id != user.id:
        raise http_error_invalid_passkey_challenge()

    verification = verify_registration(credential=body.credential, challenge=challenge)
    row = AuthWebAuthnCredential(
        user_id=user.id,
        credential_id=bytes(verification.credential_id),
        public_key=bytes(verification.credential_public_key),
        sign_count=int(verification.sign_count),
        transports=transports_from_credential(body.credential),
        aaguid=_aaguid_text(getattr(verification, "aaguid", None)),
        device_name=_device_label(body.device_name),
        backed_up=bool(getattr(verification, "credential_backed_up", False)),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise http_error_passkey_already_registered() from None
    db.refresh(row)
    return _item(row)


@router.post("/authenticate/options", response_model=PasskeyOptionsResponse)
def authenticate_options(
    body: PasskeyAuthenticateOptionsRequest = PasskeyAuthenticateOptionsRequest(),
    db: Session = Depends(get_db),
) -> PasskeyOptionsResponse:
    """Challenge di login. Identifier opzionale; senza, passkey discoverable (Face ID)."""
    ident = normalize_login_identifier(body.identifier) if body.identifier else ""
    user: AuthUser | None = None
    credentials: list[AuthWebAuthnCredential] = []
    if ident:
        user = db.scalar(
            select(AuthUser).where(or_(AuthUser.email == ident, AuthUser.username == ident))
        )
        if user is not None:
            credentials = _credentials_for_user(db, user.id)

    options, challenge_token = build_authentication_options(
        credentials=credentials,
        user_id=user.id if user is not None else None,
    )
    return PasskeyOptionsResponse(options=options, challenge_token=challenge_token)


@router.post("/authenticate", response_model=TokenResponse)
def authenticate_passkey(
    body: PasskeyAuthenticateRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Verifica l'asserzione e emette la stessa coppia token del login password."""
    challenge, token_user_id = decode_challenge_token(body.challenge_token, purpose="authenticate")
    credential_id = credential_id_from_assertion(body.credential)
    row = db.scalar(
        select(AuthWebAuthnCredential).where(AuthWebAuthnCredential.credential_id == credential_id)
    )
    if row is None:
        raise http_error_invalid_credentials()
    if token_user_id is not None and row.user_id != token_user_id:
        raise http_error_invalid_credentials()

    user = db.get(AuthUser, row.user_id)
    if user is None:
        raise http_error_invalid_credentials()
    raise_if_cannot_login(user)

    verification = verify_authentication(
        credential=body.credential,
        challenge=challenge,
        public_key=bytes(row.public_key),
        sign_count=int(row.sign_count or 0),
    )
    row.sign_count = int(verification.new_sign_count)
    row.last_used_at = datetime.now(tz=UTC)
    db.add(row)
    sync_profile_incomplete_notification(db, user)

    try:
        token_response = build_token_response(db, user)
    except ValueError:
        db.rollback()
        raise http_error_auth_not_configured() from None
    db.commit()
    return token_response


@router.get("", response_model=PasskeyListResponse)
def list_passkeys(user: AuthenticatedUser, db: Session = Depends(get_db)) -> PasskeyListResponse:
    """Elenco passkey dell'utente corrente."""
    return PasskeyListResponse(items=[_item(row) for row in _credentials_for_user(db, user.id)])


@router.delete("/{passkey_id}", response_model=PasskeyDeleteResponse)
def delete_passkey(
    passkey_id: uuid.UUID,
    user: AuthenticatedUser,
    db: Session = Depends(get_db),
) -> PasskeyDeleteResponse:
    """Revoca una passkey. Blocca se sarebbe l'ultimo metodo di accesso."""
    row = db.scalar(
        select(AuthWebAuthnCredential).where(
            AuthWebAuthnCredential.id == passkey_id,
            AuthWebAuthnCredential.user_id == user.id,
        )
    )
    if row is None:
        raise http_error_passkey_not_found()
    if count_login_methods(db, user, exclude_passkey_id=row.id) < 1:
        raise http_error_cannot_delete_last_login()
    db.delete(row)
    db.commit()
    return PasskeyDeleteResponse()
