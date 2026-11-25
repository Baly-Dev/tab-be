"""Dipendenze FastAPI per autorizzazione (permessi su ruoli)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth.models.user import AuthUser
from auth.utils.helpers import AuthenticatedUser, get_current_user
from config.constants import AppRole
from config.db.session import get_db
from core.permissions import Permission, user_has_permission
from core.utils.roles import load_user_roles


def require_permission(permission: Permission) -> Callable[..., AuthUser]:
    """Factory: dependency che richiede ``permission`` oltre all'autenticazione."""

    def _dependency(
        user: AuthenticatedUser,
        db: Session = Depends(get_db),
    ) -> AuthUser:
        """Verifica permesso; 403 con codice stabile per il FE."""
        if not user_has_permission(db, user.id, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "permission_denied",
                    "message": "You do not have permission to perform this action",
                    "required_permission": permission.value,
                },
            )
        return user

    return _dependency


AdminReadUser = Annotated[AuthUser, Depends(require_permission(Permission.ADMIN_READ))]
AdminWriteUser = Annotated[AuthUser, Depends(require_permission(Permission.ADMIN_WRITE))]
AdminLogsUser = Annotated[AuthUser, Depends(require_permission(Permission.ADMIN_LOGS))]


def require_super_admin() -> Callable[..., AuthUser]:
    """Solo ``super_admin`` (audience CRM, export sensibili, ecc.)."""

    def _dependency(
        user: AuthenticatedUser,
        db: Session = Depends(get_db),
    ) -> AuthUser:
        if AppRole.SUPER_ADMIN.value not in load_user_roles(db, user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "super_admin_required",
                    "message": "Solo il super admin può accedere a questa risorsa",
                },
            )
        return user

    return _dependency


SuperAdminUser = Annotated[AuthUser, Depends(require_super_admin())]
