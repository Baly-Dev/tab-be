"""Visibilità profilo: dettagli solo per sé stessi o connessioni accepted."""

from __future__ import annotations

import uuid

from core.models.connection import CoreProfileConnection
from core.utils.connections import is_accepted_connection


def can_view_full_profile(
    *,
    viewer_id: uuid.UUID,
    subject_id: uuid.UUID,
    connection: CoreProfileConnection | None,
) -> bool:
    """True se il viewer può vedere bio, lavoro, sede, interessi ed eventi del subject."""
    if viewer_id == subject_id:
        return True
    return is_accepted_connection(connection)
