"""Hash e verifica password (bcrypt TrustNet + hash WordPress in lettura).

I nuovi hash sono sempre bcrypt nativo (``hash_password``). In verifica si accettano
anche gli hash WP migrati; al primo login valido si fa upgrade a bcrypt TN.

Formati WP (``wp_check_password`` / ``wp_hash_password`` da WordPress 6.8):

- ``$wp$2y$…`` / ``$wp$2a$…`` / ``$wp$2b$…`` — bcrypt del pre-hash
  ``base64(HMAC-SHA384(password, key=wp-sha384))``; il prefisso ``$wp`` si toglie
  prima di ``bcrypt.checkpw``.
- ``$P$`` / ``$H$`` — phpass portable (MD5 iterato), sale nel hash.
- 32 caratteri — MD5 legacy WP.
- ``$2y$`` / ``$2a$`` / ``$2b$`` senza ``$wp`` — bcrypt sulla password in chiaro.

Non servono ``AUTH_KEY`` / salt di ``wp-config.php``: il sale è nel hash.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Any

import bcrypt
from passlib.hash import phpass

_WP_HMAC_KEY = b"wp-sha384"
_TN_BCRYPT_PREFIX = "$2b$12$"


def hash_password(plain: str) -> str:
    """Hash bcrypt TrustNet (cost 12). Unico writer per password nuove."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def needs_rehash(password_hash: str) -> bool:
    """True se l'hash non è bcrypt TN a cost 12 (legacy WP o cost diverso)."""
    return not password_hash.startswith(_TN_BCRYPT_PREFIX)


def verify_password(plain: str, password_hash: str) -> bool:
    """Verifica ``plain`` contro hash TN o WordPress. False su formato ignoto."""
    if not plain or not password_hash:
        return False
    stored = password_hash.strip()
    if not stored:
        return False
    try:
        if stored.startswith("$wp"):
            return _verify_wp_prefixed_bcrypt(plain, stored)
        if stored.startswith("$P$") or stored.startswith("$H$"):
            return bool(phpass.verify(plain, stored))
        if len(stored) <= 32:
            digest = hashlib.md5(plain.encode("utf-8")).hexdigest()
            return hmac.compare_digest(digest, stored.lower())
        return bcrypt.checkpw(plain.encode("utf-8"), stored.encode("ascii"))
    except (ValueError, TypeError):
        return False


def upgrade_password_hash_if_needed(user: Any, plain: str) -> None:
    """Se l'hash è legacy WP, riscrive bcrypt TN. Chiamare solo dopo verify ok."""
    stored = getattr(user, "password_hash", None)
    if not stored or not needs_rehash(str(stored)):
        return
    user.password_hash = hash_password(plain)


def _verify_wp_prefixed_bcrypt(plain: str, stored: str) -> bool:
    """``$wp`` + bcrypt(HMAC-SHA384) come in ``wp_check_password`` WP 6.8+."""
    bcrypt_hash = stored[3:]
    if not bcrypt_hash.startswith("$2"):
        return False
    prehashed = _wp_prehash(plain)
    return bcrypt.checkpw(prehashed, bcrypt_hash.encode("ascii"))


def _wp_prehash(plain: str) -> bytes:
    digest = hmac.new(_WP_HMAC_KEY, plain.encode("utf-8"), hashlib.sha384).digest()
    return base64.b64encode(digest)
