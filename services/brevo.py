"""Brevo client for auth emails: verification, welcome, password reset."""

from __future__ import annotations

import logging
import uuid
from functools import lru_cache
from typing import Any
from urllib.parse import urlencode

import httpx

from auth.utils.tokens import create_email_verify_token
from config import Settings, get_settings

logger = logging.getLogger(__name__)

BREVO_API_BASE = "https://api.brevo.com/v3"
BREVO_SMTP_EMAIL_URL = f"{BREVO_API_BASE}/smtp/email"


class BrevoService:
    """Transactional email via Brevo templates."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def is_configured(self) -> bool:
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

    def send(
        self,
        *,
        to_email: str,
        template_id: int,
        params: dict[str, str],
    ) -> None:
        """Send a transactional template. Empty API key logs and returns."""
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
        token = create_email_verify_token(user_id, email)
        base = self._settings.email_verification_frontend_url
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}{urlencode({'token': token})}"

    def _verification_template_params(self, *, link: str, first_name: str) -> dict[str, str]:
        safe_name = first_name.strip() or "there"
        link_key = self._settings.brevo_email_verification_link_param.strip() or "verification_url"
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
        if not self.is_configured:
            logger.warning("BREVO_API_KEY empty; skip password reset email to %s", email)
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
        try:
            self.send(to_email=email, template_id=template_id, params=params)
        except Exception:
            logger.exception("Failed to send password reset email to %s", email)
            raise

    def build_welcome_link(self) -> str:
        return self._settings.app_frontend_url.strip().rstrip("/")

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
        self.send_welcome_email(email=email, first_name=first_name)

    def send_password_reset_email_task(
        self,
        email: str,
        plain_token: str,
        first_name: str,
    ) -> None:
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
    get_brevo_service().send_password_reset_email_task(
        email=email,
        plain_token=plain_token,
        first_name=first_name,
    )


@lru_cache
def get_brevo_service() -> BrevoService:
    return BrevoService()
