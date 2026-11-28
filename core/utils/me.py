"""Costruzione risposta GET /core/me."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models.social_account import AuthSocialAccount
from auth.models.user import AuthUser
from auth.models.webauthn_credential import AuthWebAuthnCredential
from auth.utils.invites import count_signup_invites
from auth.utils.registration import is_registration_complete
from core.utils.roles import load_user_roles
from config.constants import ConnectionStatus
from core.models.connection import CoreProfileConnection
from core.models.interest import CoreInterest
from core.models.profile import CoreProfile
from core.models.user_interest import CoreUserInterest
from core.schemas.me import (
    LinkedAccountItem,
    MeConnectionsSummary,
    MeInterestItem,
    MeProfileResponse,
    MeResponse,
)
from services.storage import public_asset_url


async def build_me_response(db: AsyncSession, user: AuthUser) -> MeResponse:
    """Carica profilo, interessi e ruoli per l'utente autenticato."""
    profile_row = await db.get(CoreProfile, user.id)
    profile = _profile_to_schema(profile_row) if profile_row is not None else None

    interest_rows = await db.execute(
        select(CoreInterest.id, CoreInterest.name)
        .join(CoreUserInterest, CoreUserInterest.interest_id == CoreInterest.id)
        .where(CoreUserInterest.user_id == user.id)
        .order_by(CoreInterest.sort_order, CoreInterest.name)
    ).all()
    interests = [MeInterestItem(id=row.id, name=str(row.name)) for row in interest_rows]

    social_rows = (await db.scalars(
        select(AuthSocialAccount).where(AuthSocialAccount.user_id == user.id)
    )).all()
    social_sorted = sorted(social_rows, key=lambda row: row.provider.value)
    linked_providers = [row.provider.value for row in social_sorted]
    linked_accounts = [
        LinkedAccountItem(
            provider=row.provider.value,
            email=str(row.email) if row.email else None,
        )
        for row in social_sorted
    ]
    has_passkeys = (
        await db.scalar(
            select(AuthWebAuthnCredential.id)
            .where(AuthWebAuthnCredential.user_id == user.id)
            .limit(1)
        )
        is not None
    )

    return MeResponse(
        id=user.id,
        email=str(user.email),
        username=str(user.username),
        status=user.status.value,
        referral_code=str(user.referral_code),
        invites_count=count_signup_invites(db, user.id),
        has_password=user.has_password,
        has_passkeys=has_passkeys,
        email_verified_at=user.email_verified_at,
        registration_complete=await is_registration_complete(db, user.id),
        roles=await load_user_roles(db, user.id),
        linked_providers=linked_providers,
        linked_accounts=linked_accounts,
        connections=_load_connections_summary(db, user.id),
        interests=interests,
        profile=profile,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _profile_to_schema(row: CoreProfile) -> MeProfileResponse:
    """Mappa riga ORM → schema API."""
    return MeProfileResponse(
        first_name=str(row.first_name),
        last_name=str(row.last_name),
        birth_date=row.birth_date,
        gender=row.gender,
        marketing_consent=bool(row.marketing_consent),
        residence_country=row.residence_country,
        residence_city=row.residence_city,
        office_city=row.office_city,
        office_neighborhood=row.office_neighborhood,
        bio=row.bio,
        avatar_url=public_asset_url(row.avatar_url),
        current_company_name=row.current_company_name,
        current_job_position=row.current_job_position,
        linkedin_url=row.linkedin_url,
        preferred_cuisine=row.preferred_cuisine,
        preferred_price_band=(
            row.preferred_price_band.value
            if row.preferred_price_band is not None
            else None
        ),
        max_distance_meters=row.max_distance_meters,
        dietary_notes=row.dietary_notes,
        prefers_meal_vouchers=bool(row.prefers_meal_vouchers),
        profile_completeness=int(row.profile_completeness or 0),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _load_connections_summary(db: AsyncSession, user_id: uuid.UUID) -> MeConnectionsSummary:
    """Conta connessioni per stato dove l'utente è ``user_low`` o ``user_high``."""
    pair_filter = or_(
        CoreProfileConnection.user_low_id == user_id,
        CoreProfileConnection.user_high_id == user_id,
    )
    rows = await db.execute(
        select(CoreProfileConnection.status, func.count())
        .where(pair_filter)
        .group_by(CoreProfileConnection.status)
    ).all()
    counts: dict[ConnectionStatus, int] = {}
    for status, count in rows:
        key = status if isinstance(status, ConnectionStatus) else ConnectionStatus(str(status))
        counts[key] = int(count)
    return MeConnectionsSummary(
        accepted=counts.get(ConnectionStatus.ACCEPTED, 0),
        pending=counts.get(ConnectionStatus.PENDING, 0),
        blocked=counts.get(ConnectionStatus.BLOCKED, 0),
    )
