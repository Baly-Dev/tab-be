"""Hard-delete account: la riga ``auth_users`` sparisce, i figli CASCADE."""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from auth.models.social_account import AuthSocialAccount
from auth.models.user import AuthUser
from auth.utils.account_erasure import erase_retained_personal_data
from auth.utils.tokens import revoke_all_refresh_tokens_for_user


class AccountPurgeError(Exception):
    """Impossibile eliminare l'account."""

    def __init__(self, message: str = "Could not delete account") -> None:
        self.message = message
        super().__init__(message)


def purge_auth_user(db: Session, user: AuthUser) -> None:
    """Elimina l'utente dal DB.

    Prima rimuove avatar, snapshot nelle notifiche e identificativi negli audit log.
    """
    user_id = user.id
    erase_retained_personal_data(db, user)
    db.execute(delete(AuthSocialAccount).where(AuthSocialAccount.user_id == user_id))
    revoke_all_refresh_tokens_for_user(db, user_id)
    db.delete(user)
