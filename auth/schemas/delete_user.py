"""Schemi cancellazione utente."""

import uuid

from pydantic import BaseModel


class DeleteUserResponse(BaseModel):
    """Utente e dati collegati rimossi (cascade DB)."""

    user_id: uuid.UUID
    deleted: bool = True
