"""Client Brevo (Sendinblue): template transazionali e email di dominio."""

from __future__ import annotations

import logging
import uuid
from functools import lru_cache
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx

from auth.utils.tokens import create_email_verify_token
from config import Settings, get_settings

logger = logging.getLogger(__name__)

BREVO_API_BASE = "https://api.brevo.com/v3"
BREVO_SMTP_EMAIL_URL = f"{BREVO_API_BASE}/smtp/email"


class BrevoService:
    """Invio email via API Brevo (template + params)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def is_configured(self) -> bool:
        """True se ``BREVO_API_KEY`` è valorizzata."""
        return bool(self._settings.brevo_api_key.strip())

    def _api_key(self) -> str | None:
        key = self._settings.brevo_api_key.strip()
        return key or None

    def _request_headers(self) -> dict[str, str]:
        key = self._api_key()
        if not key:
            raise ValueError("BREVO_API_KEY is not configured")
        return {
            "accept": "application/json",
            "api-key": key,
            "content-type": "application/json",
        }

    def _http_client(self) -> httpx.Client:
        return httpx.Client(timeout=30.0)

    def get_template(self, template_id: int) -> dict[str, Any]:
        """Recupera un template SMTP transazionale da Brevo (``GET /v3/smtp/templates/{id}``)."""
        if template_id <= 0:
            raise ValueError("template_id must be a positive integer")
        url = f"{BREVO_API_BASE}/smtp/templates/{template_id}"
        with self._http_client() as client:
            response = client.get(url, headers=self._request_headers())
            response.raise_for_status()
            return response.json()

    def send(
        self,
        *,
        to_email: str,
        template_id: int,
        params: dict[str, str],
    ) -> None:
        """Invia email transazionale con ``templateId`` e ``params``.

        Se ``BREVO_API_KEY`` è vuota: log e no-op (dev locale).
        ``EMAIL_SENDER_*`` opzionale se il mittente è già nel template Brevo.
        """
        if not self.is_configured:
            logger.warning("BREVO_API_KEY empty; skip transactional template email to %s", to_email)
            return
        if template_id <= 0:
            raise ValueError("template_id must be a positive integer")

        payload: dict[str, Any] = {
            "to": [{"email": to_email}],
            "templateId": template_id,
            "params": params,
        }
        sender_email = self._settings.email_sender_email.strip()
        if sender_email:
            payload["sender"] = {
                "name": self._settings.email_sender_name,
                "email": sender_email,
            }

        with self._http_client() as client:
            response = client.post(
                BREVO_SMTP_EMAIL_URL,
                json=payload,
                headers=self._request_headers(),
            )
            if not response.is_success:
                logger.error(
                    "Brevo send failed status=%s template_id=%s to=%s body=%s",
                    response.status_code,
                    template_id,
                    to_email,
                    response.text,
                )
            response.raise_for_status()

    def build_verification_link(self, user_id: uuid.UUID, email: str) -> str:
        """URL FE con query ``token`` (JWT verifica email)."""
        token = create_email_verify_token(user_id, email)
        base = self._settings.email_verification_frontend_url
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}{urlencode({'token': token})}"

    def _verification_template_params(self, *, link: str, first_name: str) -> dict[str, str]:
        safe_name = first_name.strip() or "there"
        link_key = (
            self._settings.brevo_email_verification_link_param.strip() or "verification_url"
        )
        params: dict[str, str] = {link_key: link}
        first_param = self._settings.brevo_email_verification_first_name_param.strip()
        if first_param:
            params[first_param] = safe_name
        return params

    def send_verification_email(
        self,
        *,
        user_id: uuid.UUID,
        email: str,
        first_name: str,
    ) -> None:
        """Email post-signup / resend: template Brevo + param link con JWT."""
        if not self.is_configured:
            return

        template_id = self._settings.brevo_email_verification_template_id
        if template_id <= 0:
            logger.warning(
                "BREVO_EMAIL_VERIFICATION_TEMPLATE_ID invalid; skip verification email to %s",
                email,
            )
            return

        try:
            link = self.build_verification_link(user_id, email)
        except ValueError as exc:
            logger.warning("Skip verification email (misconfiguration): %s", exc)
            return

        params = self._verification_template_params(link=link, first_name=first_name)
        try:
            self.send(to_email=email, template_id=template_id, params=params)
        except Exception:
            logger.exception("Failed to send verification email to %s", email)

    def build_password_reset_link(self, plain_token: str) -> str:
        """URL FE con query ``token`` (opaco monouso)."""
        base = self._settings.password_reset_frontend_url.strip()
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}{urlencode({'token': plain_token})}"

    def _password_reset_template_params(self, *, link: str, first_name: str) -> dict[str, str]:
        safe_name = first_name.strip() or "there"
        link_key = self._settings.brevo_password_reset_link_param.strip() or "reset_url"
        params: dict[str, str] = {link_key: link}
        first_param = self._settings.brevo_password_reset_first_name_param.strip()
        if first_param:
            params[first_param] = safe_name
        return params

    def send_password_reset_email(
        self,
        *,
        email: str,
        plain_token: str,
        first_name: str,
    ) -> None:
        """Email reset password via template Brevo."""
        if not self.is_configured:
            logger.warning(
                "BREVO_API_KEY empty; skip password reset email to %s",
                email,
            )
            return
        template_id = self._settings.brevo_password_reset_template_id
        if template_id <= 0:
            logger.warning(
                "BREVO_PASSWORD_RESET_TEMPLATE_ID=%s invalid; skip password reset email to %s",
                template_id,
                email,
            )
            return
        link = self.build_password_reset_link(plain_token)
        params = self._password_reset_template_params(link=link, first_name=first_name)
        logger.info(
            "Sending password reset email to %s (template_id=%s, params_keys=%s)",
            email,
            template_id,
            list(params.keys()),
        )
        try:
            self.send(to_email=email, template_id=template_id, params=params)
        except Exception:
            logger.exception("Failed to send password reset email to %s", email)
            raise

    def _event_template_params(
        self,
        *,
        link: str,
        first_name: str,
        event_title: str,
        extra_params: dict[str, str] | None = None,
    ) -> dict[str, str]:
        safe_name = first_name.strip() or "there"
        params: dict[str, str] = {
            key: value for key, value in (extra_params or {}).items() if value
        }
        params[self._settings.brevo_event_link_param.strip() or "event_url"] = link
        params[self._settings.brevo_event_title_param.strip() or "event_title"] = event_title
        first_param = self._settings.brevo_event_first_name_param.strip()
        if first_param:
            params[first_param] = safe_name
        return params

    def build_event_detail_link(self, event_slug: str) -> str:
        base = self._settings.event_detail_frontend_url.strip().rstrip("/")
        return f"{base}/{event_slug}"

    def build_frontend_link(self, path: str) -> str:
        """Link assoluto sul frontend a partire da ``EVENT_DETAIL_FRONTEND_URL``."""
        base = self._settings.event_detail_frontend_url.strip()
        parsed = urlsplit(base)
        origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        suffix = path if path.startswith("/") else f"/{path}"
        return f"{origin}{suffix}"

    def _send_event_registration_email(
        self,
        *,
        email: str,
        first_name: str,
        event_title: str,
        event_slug: str,
        template_id: int,
        kind_label: str,
        extra_params: dict[str, str] | None = None,
    ) -> None:
        """Invio template evento (params: event_url, event_title, first_name + dati evento)."""
        if not self.is_configured or template_id <= 0:
            logger.warning(
                "Skip event %s email to %s (Brevo not configured)",
                kind_label,
                email,
            )
            return
        link = self.build_event_detail_link(event_slug)
        params = self._event_template_params(
            link=link,
            first_name=first_name,
            event_title=event_title,
            extra_params=extra_params,
        )
        try:
            self.send(to_email=email, template_id=template_id, params=params)
        except Exception:
            logger.exception("Failed to send event %s email to %s", kind_label, email)

    def send_event_confirmation_request_email(
        self,
        *,
        email: str,
        first_name: str,
        event_title: str,
        event_slug: str,
        extra_params: dict[str, str] | None = None,
    ) -> None:
        """Richiesta automatica di conferma, nella finestra prima dell'evento."""
        self._send_event_registration_email(
            email=email,
            first_name=first_name,
            event_title=event_title,
            event_slug=event_slug,
            template_id=self._settings.brevo_event_confirmation_request_template_id,
            kind_label="confirmation_request",
            extra_params=extra_params,
        )

    def send_event_confirmation_reminder_email(
        self,
        *,
        email: str,
        first_name: str,
        event_title: str,
        event_slug: str,
        extra_params: dict[str, str] | None = None,
    ) -> None:
        """Mail inviata quando l'utente conferma la partecipazione."""
        self._send_event_registration_email(
            email=email,
            first_name=first_name,
            event_title=event_title,
            event_slug=event_slug,
            template_id=self._settings.brevo_event_confirmation_reminder_template_id,
            kind_label="confirmation_reminder",
            extra_params=extra_params,
        )

    def send_event_confirmation_followup_email(
        self,
        *,
        email: str,
        first_name: str,
        event_title: str,
        event_slug: str,
        extra_params: dict[str, str] | None = None,
    ) -> None:
        """Follow-up di conferma, inviato dal bottone Reinvia in console."""
        self._send_event_registration_email(
            email=email,
            first_name=first_name,
            event_title=event_title,
            event_slug=event_slug,
            template_id=self._settings.brevo_event_confirmation_followup_template_id,
            kind_label="confirmation_followup",
            extra_params=extra_params,
        )

    def send_event_confirmation_expired_email(
        self,
        *,
        email: str,
        first_name: str,
        event_title: str,
        event_slug: str,
        extra_params: dict[str, str] | None = None,
    ) -> None:
        """Conferma scaduta, inviata dal bottone Annulla in console."""
        self._send_event_registration_email(
            email=email,
            first_name=first_name,
            event_title=event_title,
            event_slug=event_slug,
            template_id=self._settings.brevo_event_confirmation_expired_template_id,
            kind_label="confirmation_expired",
            extra_params=extra_params,
        )

    def send_event_waitlist_promoted_email(
        self,
        *,
        email: str,
        first_name: str,
        event_title: str,
        event_slug: str,
        extra_params: dict[str, str] | None = None,
    ) -> None:
        """Notifica promozione da waitlist a iscritto effettivo."""
        self._send_event_registration_email(
            email=email,
            first_name=first_name,
            event_title=event_title,
            event_slug=event_slug,
            template_id=self._settings.brevo_event_waitlist_promoted_template_id,
            kind_label="waitlist_promoted",
            extra_params=extra_params,
        )

    def send_event_reminder_email(
        self,
        *,
        email: str,
        first_name: str,
        event_title: str,
        event_slug: str,
        extra_params: dict[str, str] | None = None,
    ) -> None:
        """Reminder pre-evento agli iscritti confirmed."""
        self._send_event_registration_email(
            email=email,
            first_name=first_name,
            event_title=event_title,
            event_slug=event_slug,
            template_id=self._settings.brevo_event_reminder_template_id,
            kind_label="event_reminder",
            extra_params=extra_params,
        )

    def send_event_waitlist_joined_email(
        self,
        *,
        email: str,
        first_name: str,
        event_title: str,
        event_slug: str,
        extra_params: dict[str, str] | None = None,
    ) -> None:
        """Conferma ingresso in waitlist."""
        self._send_event_registration_email(
            email=email,
            first_name=first_name,
            event_title=event_title,
            event_slug=event_slug,
            template_id=self._settings.brevo_event_waitlist_joined_template_id,
            kind_label="waitlist_joined",
            extra_params=extra_params,
        )

    def send_event_registration_auto_cancelled_email(
        self,
        *,
        email: str,
        first_name: str,
        event_title: str,
        event_slug: str,
        extra_params: dict[str, str] | None = None,
    ) -> None:
        """Cancellazione volontaria dell'iscrizione da parte dell'utente."""
        self._send_event_registration_email(
            email=email,
            first_name=first_name,
            event_title=event_title,
            event_slug=event_slug,
            template_id=self._settings.brevo_event_registration_auto_cancelled_template_id,
            kind_label="registration_auto_cancelled",
            extra_params=extra_params,
        )

    def send_event_registration_system_cancelled_email(
        self,
        *,
        email: str,
        first_name: str,
        event_title: str,
        event_slug: str,
        extra_params: dict[str, str] | None = None,
    ) -> None:
        """Cancellazione da sistema o host, per esempio evento archiviato."""
        self._send_event_registration_email(
            email=email,
            first_name=first_name,
            event_title=event_title,
            event_slug=event_slug,
            template_id=self._settings.brevo_event_registration_system_cancelled_template_id,
            kind_label="registration_system_cancelled",
            extra_params=extra_params,
        )

    def send_connection_request_email(
        self,
        *,
        email: str,
        first_name: str,
        actor_name: str,
        actor_first_name: str,
    ) -> None:
        """Richiesta di connessione: il destinatario è chi riceve la richiesta."""
        template_id = self._settings.brevo_connection_request_template_id
        if not self.is_configured or template_id <= 0:
            logger.warning(
                "Skip connection request email to %s (Brevo not configured, template_id=%s)",
                email,
                template_id,
            )
            return
        safe_name = first_name.strip() or "there"
        params: dict[str, str] = {
            "first_name": safe_name,
            "connection_url": self.build_frontend_link("/network?scope=incoming"),
        }
        if actor_name.strip():
            params["actor_name"] = actor_name.strip()
        if actor_first_name.strip():
            params["actor_first_name"] = actor_first_name.strip()
        try:
            self.send(to_email=email, template_id=template_id, params=params)
        except Exception:
            logger.exception("Failed to send connection request email to %s", email)

    def send_connection_event_alert_email(
        self,
        *,
        email: str,
        first_name: str,
        event_title: str,
        event_slug: str,
        cancelled: bool,
        extra_params: dict[str, str] | None = None,
    ) -> None:
        """Campanella: un contatto si iscrive, entra in waitlist o annulla."""
        template_id = (
            self._settings.brevo_connection_event_cancelled_template_id
            if cancelled
            else self._settings.brevo_connection_event_registered_template_id
        )
        kind_label = "connection_event_cancelled" if cancelled else "connection_event_registered"
        self._send_event_registration_email(
            email=email,
            first_name=first_name,
            event_title=event_title,
            event_slug=event_slug,
            template_id=template_id,
            kind_label=kind_label,
            extra_params=extra_params,
        )

    def send_event_registration_confirmed_email(
        self,
        *,
        email: str,
        first_name: str,
        event_title: str,
        event_slug: str,
        extra_params: dict[str, str] | None = None,
    ) -> None:
        """Ricevuta iscrizione confermata."""
        self._send_event_registration_email(
            email=email,
            first_name=first_name,
            event_title=event_title,
            event_slug=event_slug,
            template_id=self._settings.brevo_event_registration_confirmed_template_id,
            kind_label="registration_confirmed",
            extra_params=extra_params,
        )

    def build_welcome_link(self) -> str:
        """CTA post-registrazione: listing eventi."""
        return self._settings.event_detail_frontend_url.strip().rstrip("/")

    def _welcome_template_params(self, *, first_name: str, link: str) -> dict[str, str]:
        safe_name = first_name.strip() or "there"
        params: dict[str, str] = {}
        first_param = self._settings.brevo_welcome_first_name_param.strip()
        if first_param:
            params[first_param] = safe_name
        link_key = self._settings.brevo_welcome_link_param.strip() or "app_url"
        params[link_key] = link
        return params

    def send_welcome_email(self, *, email: str, first_name: str) -> None:
        """Welcome dopo registrazione completata (verifica email o wizard OAuth)."""
        if not self.is_configured:
            logger.warning("BREVO_API_KEY empty; skip welcome email to %s", email)
            return
        template_id = self._settings.brevo_welcome_template_id
        if template_id <= 0:
            logger.warning(
                "BREVO_WELCOME_TEMPLATE_ID=%s invalid; skip welcome email to %s",
                template_id,
                email,
            )
            return
        params = self._welcome_template_params(
            first_name=first_name,
            link=self.build_welcome_link(),
        )
        try:
            self.send(to_email=email, template_id=template_id, params=params)
        except Exception:
            logger.exception("Failed to send welcome email to %s", email)

    def send_welcome_email_task(self, email: str, first_name: str) -> None:
        """Per ``BackgroundTasks``: argomenti serializzabili."""
        self.send_welcome_email(email=email, first_name=first_name)

    def send_password_reset_email_task(
        self,
        email: str,
        plain_token: str,
        first_name: str,
    ) -> None:
        """Per ``BackgroundTasks``: argomenti serializzabili."""
        self.send_password_reset_email(
            email=email,
            plain_token=plain_token,
            first_name=first_name,
        )

    def send_verification_email_task(
        self,
        user_id_str: str,
        email: str,
        first_name: str,
    ) -> None:
        """Per ``BackgroundTasks``: argomenti serializzabili."""
        self.send_verification_email(
            user_id=uuid.UUID(user_id_str),
            email=email,
            first_name=first_name,
        )


def send_password_reset_email_background(
    email: str,
    plain_token: str,
    first_name: str,
) -> None:
    """Wrapper modulo per ``BackgroundTasks`` (come verify-email)."""
    get_brevo_service().send_password_reset_email_task(
        email=email,
        plain_token=plain_token,
        first_name=first_name,
    )


@lru_cache
def get_brevo_service() -> BrevoService:
    """Dependency FastAPI: istanza singleton del client Brevo."""
    return BrevoService()
