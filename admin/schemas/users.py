"""Schemi utenti console admin."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from config.constants import AppRole, UserStatus
from services.storage import PublicMediaUrl


class AdminUserSort(str, Enum):
    """Colonna di ordinamento dell'elenco utenti."""

    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    EMAIL = "email"
    CREATED_AT = "created_at"


class SortOrder(str, Enum):
    """Direzione di ordinamento."""

    ASC = "asc"
    DESC = "desc"


class AdminUserListItem(BaseModel):
    """Riga elenco utenti staff."""

    id: uuid.UUID
    username: str
    email: str
    status: str
    roles: list[str]
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: PublicMediaUrl = None
    created_at: datetime
    invited_by_id: uuid.UUID | None = None
    invites_count: int = 0
    connections_accepted: int = 0
    pending_reason: str | None = Field(
        default=None,
        description="Perché ``status=pending``: email_verification | oauth_onboarding | incomplete. Solo super_admin.",
    )


class AdminUserDetail(AdminUserListItem):
    """Dettaglio utente in console."""

    email_verified_at: datetime | None = None
    registration_complete: bool = False
    invited_by_username: str | None = None


class AdminUserListResponse(BaseModel):
    """Pagina elenco utenti."""

    items: list[AdminUserListItem]
    total: int
    limit: int
    offset: int


class UpdateAdminUserRequest(BaseModel):
    """Mutazione utente (solo super_admin)."""

    status: UserStatus | None = None
    roles: list[AppRole] | None = Field(
        default=None,
        description="Sostituisce l'insieme ruoli; almeno un ruolo.",
    )


class LinkAdminSignupInviteRequest(BaseModel):
    """Attribuisce un utente come invitato da questo account (solo super_admin)."""

    invitee_id: uuid.UUID = Field(description="Utente B da collegare come se fosse stato invitato.")


class AdminUserDeletedResponse(BaseModel):
    """Esito eliminazione account (riga rimossa)."""

    user_id: uuid.UUID
    deleted: bool = True


class UserExportMode(str, Enum):
    """Tipo di export CSV utenti."""

    GLOBAL = "global"
    CUSTOM = "custom"


class UserExportColumn(str, Enum):
    """Colonne esportabili (allowlist)."""

    ID = "id"
    EMAIL = "email"
    USERNAME = "username"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    STATUS = "status"
    ROLES = "roles"
    CREATED_AT = "created_at"
    EMAIL_VERIFIED_AT = "email_verified_at"
    REFERRAL_CODE = "referral_code"
    INVITED_BY_USERNAME = "invited_by_username"
    BIRTH_DATE = "birth_date"
    GENDER = "gender"
    RESIDENCE_COUNTRY = "residence_country"
    RESIDENCE_CITY = "residence_city"
    BIO = "bio"
    CURRENT_COMPANY_NAME = "current_company_name"
    CURRENT_JOB_POSITION = "current_job_position"
    LINKEDIN_URL = "linkedin_url"
    INTERESTS = "interests"
    INVITES_COUNT = "invites_count"
    CONNECTIONS_ACCEPTED = "connections_accepted"
    PROFILE_COMPLETENESS = "profile_completeness"


class ExportAdminUsersRequest(BaseModel):
    """Richiesta export CSV utenti (solo super_admin)."""

    mode: UserExportMode
    columns: list[UserExportColumn] | None = Field(
        default=None,
        description="Obbligatorie per l'export custom; ignorate nel globale (tutte le colonne).",
    )

    @model_validator(mode="after")
    def validate_export(self) -> ExportAdminUsersRequest:
        if self.mode == UserExportMode.CUSTOM and not self.columns:
            raise ValueError("Select at least one column for a custom export")
        return self
