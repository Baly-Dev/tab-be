"""Lettura contatti Brevo (API Contacts)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from config import Settings, get_settings
from services.brevo import BREVO_API_BASE

logger = logging.getLogger(__name__)

BREVO_CONTACTS_URL = f"{BREVO_API_BASE}/contacts"
_PAGE_SIZE = 500


@dataclass(frozen=True, slots=True)
class BrevoContactRow:
    email: str
    first_name: str | None
    last_name: str | None


class BrevoContactsError(Exception):
    """Errore HTTP o risposta non valida da Brevo Contacts."""


def parse_brevo_list_ids(raw: str) -> list[int]:
    """Da env ``1, 2,3`` → ``[1, 2, 3]``."""
    ids: list[int] = []
    for part in raw.split(","):
        piece = part.strip()
        if not piece:
            continue
        try:
            value = int(piece)
        except ValueError:
            continue
        if value > 0:
            ids.append(value)
    return ids


def _attribute(attributes: dict[str, Any], *keys: str) -> str | None:
    lowered = {str(k).upper(): v for k, v in attributes.items()}
    for key in keys:
        value = lowered.get(key.upper())
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _row_from_payload(item: dict[str, Any]) -> BrevoContactRow | None:
    email = str(item.get("email") or "").strip()
    if not email:
        return None
    attributes = item.get("attributes")
    if not isinstance(attributes, dict):
        attributes = {}
    return BrevoContactRow(
        email=email,
        first_name=_attribute(attributes, "FIRSTNAME", "PRENOM", "NOME"),
        last_name=_attribute(attributes, "LASTNAME", "NOM", "COGNOME"),
    )


class BrevoContactsClient:
    """Client paginato per ``GET /v3/contacts``."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def is_configured(self) -> bool:
        return bool(self._settings.brevo_api_key.strip())

    def list_ids_filter(self) -> list[int]:
        return parse_brevo_list_ids(self._settings.brevo_crm_list_ids)

    def fetch_all(self) -> list[BrevoContactRow]:
        """Scarica tutti i contatti (deduplica per email, ultima occorrenza vince)."""
        if not self.is_configured:
            raise BrevoContactsError("BREVO_API_KEY is not configured")

        key = self._settings.brevo_api_key.strip()
        headers = {
            "accept": "application/json",
            "api-key": key,
        }
        list_ids = self.list_ids_filter()
        by_email: dict[str, BrevoContactRow] = {}
        offset = 0

        with httpx.Client(timeout=60.0) as client:
            while True:
                params: dict[str, Any] = {"limit": _PAGE_SIZE, "offset": offset}
                if list_ids:
                    params["listIds"] = list_ids
                response = client.get(BREVO_CONTACTS_URL, headers=headers, params=params)
                if not response.is_success:
                    logger.error(
                        "Brevo contacts fetch failed status=%s body=%s",
                        response.status_code,
                        response.text,
                    )
                    raise BrevoContactsError(
                        f"Brevo contacts API returned status {response.status_code}"
                    )
                payload = response.json()
                batch = payload.get("contacts")
                if not isinstance(batch, list):
                    raise BrevoContactsError("Brevo contacts response missing contacts array")
                if not batch:
                    break
                for item in batch:
                    if not isinstance(item, dict):
                        continue
                    row = _row_from_payload(item)
                    if row is None:
                        continue
                    by_email[row.email.strip().lower()] = row
                if len(batch) < _PAGE_SIZE:
                    break
                offset += _PAGE_SIZE

        return sorted(by_email.values(), key=lambda row: row.email.lower())


def get_brevo_contacts_client() -> BrevoContactsClient:
    return BrevoContactsClient()
