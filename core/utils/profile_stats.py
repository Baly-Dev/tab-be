"""Statistiche profilo pubblico (conteggi aggregati)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session


def count_user_posts(db: Session, user_id: uuid.UUID) -> int:
    """Conteggio post pubblicati dall'utente (opportunities ORCH).

    Restituisce ``0`` finché il modulo opportunity non è implementato.
    """
    _ = db, user_id
    return 0
