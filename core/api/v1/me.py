"""Profilo utente corrente (autenticato)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from auth.utils.helpers import AuthenticatedUser, AuthenticatedUserAllowPending
from config.db.session import get_db
from core.schemas.invites import SignupInviteesListResponse
from core.schemas.me import MeResponse
from core.schemas.me_update import UpdateMeRequest
from core.services.avatar_service import set_avatar_from_upload
from core.services.signup_invitees_service import list_signup_invitees
from core.utils.me import build_me_response
from core.utils.update_me import update_me

router = APIRouter()


@router.get("/me", response_model=MeResponse)
def get_me(
    user: AuthenticatedUserAllowPending,
    db: Session = Depends(get_db),
) -> MeResponse:
    """Utente loggato: credenziali, ``status``, profilo, interessi e flag ``registration_complete``.

    Accessibile anche con ``status=pending`` (onboarding OAuth / email non verificata).
    """
    return build_me_response(db, user)


@router.get(
    "/me/invites",
    response_model=SignupInviteesListResponse,
    summary="Persone iscritte con il tuo link invito",
    responses={
        401: {"description": "Non autenticato"},
        403: {"description": "Account non attivo"},
    },
)
def get_my_signup_invitees(
    user: AuthenticatedUser,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SignupInviteesListResponse:
    """Profili attribuiti al ``referral_code`` dell'utente autenticato."""
    try:
        return list_signup_invitees(db, user.id, limit=limit, offset=offset)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "internal_error", "message": "Unable to load signup invitees"},
        ) from exc


@router.patch(
    "/me",
    response_model=MeResponse,
    summary="Aggiorna profilo dell'utente autenticato",
    responses={
        401: {"description": "Non autenticato"},
        404: {"description": "Profilo non trovato"},
        422: {"description": "Validazione fallita o body vuoto"},
    },
)
def patch_me(
    body: UpdateMeRequest,
    user: AuthenticatedUser,
    db: Session = Depends(get_db),
) -> MeResponse:
    """Aggiornamento parziale di ``core_profiles`` e, se inviato, sostituzione interessi.

    Richiede account ``active``. Restituisce lo stesso payload di ``GET /me``.
    """
    return update_me(db, user, body)


@router.post(
    "/me/avatar",
    response_model=MeResponse,
    summary="Carica foto profilo",
    responses={
        401: {"description": "Non autenticato"},
        404: {"description": "Profilo non trovato"},
        413: {"description": "File troppo grande"},
        422: {"description": "Immagine non valida"},
    },
)
def post_me_avatar(
    user: AuthenticatedUserAllowPending,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
) -> MeResponse:
    """Multipart ``file``: JPG/PNG/WebP, max 5 MB. Accessibile anche con account pending."""
    try:
        return set_avatar_from_upload(db, user, file)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "internal_error", "message": "Unable to update avatar"},
        ) from exc
