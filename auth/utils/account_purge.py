"""Hard-delete account: la riga ``auth_users`` sparisce, i figli CASCADE."""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models.social_account import AuthSocialAccount
from auth.models.user import AuthUser
from auth.utils.account_erasure import erase_retained_personal_data
from auth.utils.tokens import revoke_all_refresh_tokens_for_user


class AccountPurgeError(Exception):
    """Impossibile eliminare l'account."""

    def __init__(self, message: str = "Could not delete account") -> None:
        self.message = message
        super().__init__(message)


async def purge_auth_user(db: AsyncSession, user: AuthUser) -> None:
    """Elimina l'utente dal DB.

    Prima rimuove gli avatar in storage gestito.
    """
    user_id = user.id
    await erase_retained_personal_data(db, user)
    await db.execute(delete(AuthSocialAccount).where(AuthSocialAccount.user_id == user_id))
    await revoke_all_refresh_tokens_for_user(db, user_id)
    await db.delete(user)
