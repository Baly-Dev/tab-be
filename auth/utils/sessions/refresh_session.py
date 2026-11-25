"""Sessioni refresh: store Redis (default) o fallback Postgres."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.models.refresh_token import AuthRefreshToken
from auth.models.user import AuthUser
from auth.utils.tokens import generate_refresh_token_plain, hash_refresh_token
from config import Settings, get_settings
from services.redis import RedisService, get_redis_service

logger = logging.getLogger(__name__)

KEY_PREFIX = "intranet"
REPLAY_KEY_PREFIX = f"{KEY_PREFIX}:rt_replay"


@dataclass(frozen=True)
class RefreshTokenRecord:
    """Record refresh valido (astrazione Redis / Postgres)."""

    user_id: uuid.UUID
    family_id: str | None = None


class RefreshSessionError(Exception):
    """Errore store sessioni refresh."""


class RefreshSessionService:
    """Collo di bottiglia: creazione, rotazione, revoca refresh token."""

    def __init__(
        self,
        settings: Settings | None = None,
        redis: RedisService | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._redis = redis or get_redis_service()

    @property
    def uses_redis(self) -> bool:
        return self._settings.uses_redis_refresh_store

    def _ttl_seconds(self) -> int:
        return self._settings.refresh_token_ttl_seconds

    def _rt_key(self, token_hash: str) -> str:
        return f"{KEY_PREFIX}:rt:{token_hash}"

    def _user_families_key(self, user_id: uuid.UUID) -> str:
        return f"{KEY_PREFIX}:user:{user_id}:families"

    def _family_tokens_key(self, family_id: str) -> str:
        return f"{KEY_PREFIX}:family:{family_id}:tokens"

    def _replay_key(self, token_hash: str) -> str:
        return f"{REPLAY_KEY_PREFIX}:{token_hash}"

    def persist(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        plain: str,
    ) -> RefreshTokenRecord:
        """Registra un nuovo refresh (nuova famiglia sessione)."""
        if self.uses_redis:
            family_id = self._persist_redis(user_id=user_id, plain=plain)
            return RefreshTokenRecord(user_id=user_id, family_id=family_id)
        row = self._persist_postgres(db, user_id=user_id, plain=plain)
        return RefreshTokenRecord(user_id=row.user_id)

    def find_valid(self, db: Session, *, plain: str) -> RefreshTokenRecord | None:
        """Refresh attivo per token plain, se esiste."""
        if self.uses_redis:
            return self._find_valid_redis(plain=plain)
        row = self._find_valid_postgres(db, plain=plain)
        if row is None:
            return None
        return RefreshTokenRecord(user_id=row.user_id)

    def rotate(
        self,
        db: Session,
        plain: str,
    ) -> tuple[RefreshTokenRecord, str, AuthUser] | None:
        """Ruota refresh; None se invalido. Rileva riuso (revoca famiglia)."""
        if self.uses_redis:
            return self._rotate_redis(db, plain=plain)
        return self._rotate_postgres(db, plain=plain)

    def revoke_plain(self, db: Session, plain: str) -> bool:
        """Revoca un singolo refresh."""
        if self.uses_redis:
            return self._revoke_plain_redis(plain=plain)
        return self._revoke_plain_postgres(db, plain=plain)

    def revoke_all_for_user(self, db: Session, user_id: uuid.UUID) -> int:
        """Revoca tutte le sessioni refresh dell'utente."""
        if self.uses_redis:
            return self._revoke_all_redis(user_id=user_id)
        return self._revoke_all_postgres(db, user_id=user_id)

    # --- Redis ---

    def _persist_redis(self, *, user_id: uuid.UUID, plain: str) -> str:
        family_id = str(uuid.uuid4())
        token_hash = hash_refresh_token(plain, settings=self._settings)
        ttl = self._ttl_seconds()
        client = self._redis.get_client()
        pipe = client.pipeline()
        pipe.hset(
            self._rt_key(token_hash),
            mapping={"user_id": str(user_id), "family_id": family_id},
        )
        pipe.expire(self._rt_key(token_hash), ttl)
        pipe.sadd(self._user_families_key(user_id), family_id)
        pipe.expire(self._user_families_key(user_id), ttl)
        pipe.sadd(self._family_tokens_key(family_id), token_hash)
        pipe.expire(self._family_tokens_key(family_id), ttl)
        try:
            pipe.execute()
        except RedisError as exc:
            raise RefreshSessionError("Could not persist refresh session") from exc
        return family_id

    def _find_valid_redis(self, *, plain: str) -> RefreshTokenRecord | None:
        token_hash = hash_refresh_token(plain, settings=self._settings)
        client = self._redis.get_client()
        try:
            data = client.hgetall(self._rt_key(token_hash))
        except RedisError as exc:
            raise RefreshSessionError("Could not read refresh session") from exc
        if not data:
            return None
        try:
            user_id = uuid.UUID(data["user_id"])
        except (KeyError, ValueError):
            logger.warning("Invalid refresh session payload for hash %s", token_hash[:8])
            return None
        return RefreshTokenRecord(user_id=user_id, family_id=data.get("family_id"))

    def _rotate_redis(
        self,
        db: Session,
        *,
        plain: str,
    ) -> tuple[RefreshTokenRecord, str, AuthUser] | None:
        token_hash = hash_refresh_token(plain, settings=self._settings)
        client = self._redis.get_client()
        rt_key = self._rt_key(token_hash)
        try:
            data = client.hgetall(rt_key)
        except RedisError as exc:
            raise RefreshSessionError("Could not rotate refresh session") from exc

        if not data:
            replay_family = client.get(self._replay_key(token_hash))
            if replay_family:
                logger.warning("Refresh token reuse detected for family %s", replay_family)
                self._revoke_family_redis(family_id=replay_family)
            return None

        try:
            user_id = uuid.UUID(data["user_id"])
            family_id = data["family_id"]
        except (KeyError, ValueError):
            return None

        user = db.get(AuthUser, user_id)
        if user is None:
            return None

        new_plain = generate_refresh_token_plain()
        new_hash = hash_refresh_token(new_plain, settings=self._settings)
        ttl = self._ttl_seconds()

        pipe = client.pipeline()
        pipe.delete(rt_key)
        pipe.set(self._replay_key(token_hash), family_id, ex=ttl)
        pipe.srem(self._family_tokens_key(family_id), token_hash)
        pipe.hset(
            self._rt_key(new_hash),
            mapping={"user_id": str(user_id), "family_id": family_id},
        )
        pipe.expire(self._rt_key(new_hash), ttl)
        pipe.sadd(self._family_tokens_key(family_id), new_hash)
        pipe.expire(self._family_tokens_key(family_id), ttl)
        try:
            pipe.execute()
        except RedisError as exc:
            raise RefreshSessionError("Could not rotate refresh session") from exc

        record = RefreshTokenRecord(user_id=user_id, family_id=family_id)
        return record, new_plain, user

    def _revoke_plain_redis(self, *, plain: str) -> bool:
        token_hash = hash_refresh_token(plain, settings=self._settings)
        client = self._redis.get_client()
        rt_key = self._rt_key(token_hash)
        try:
            data = client.hgetall(rt_key)
            if not data:
                return False
            family_id = data.get("family_id", "")
            ttl = self._ttl_seconds()
            pipe = client.pipeline()
            pipe.delete(rt_key)
            if family_id:
                pipe.set(self._replay_key(token_hash), family_id, ex=ttl)
                pipe.srem(self._family_tokens_key(family_id), token_hash)
            pipe.execute()
        except RedisError as exc:
            raise RefreshSessionError("Could not revoke refresh session") from exc
        return True

    def _revoke_all_redis(self, *, user_id: uuid.UUID) -> int:
        client = self._redis.get_client()
        families_key = self._user_families_key(user_id)
        try:
            families = list(client.smembers(families_key))
            count = 0
            for family_id in families:
                count += self._revoke_family_redis(family_id=family_id)
            client.delete(families_key)
        except RedisError as exc:
            raise RefreshSessionError("Could not revoke user sessions") from exc
        return count

    def _revoke_family_redis(self, *, family_id: str) -> int:
        client = self._redis.get_client()
        family_key = self._family_tokens_key(family_id)
        ttl = self._ttl_seconds()
        try:
            token_hashes = list(client.smembers(family_key))
            if not token_hashes:
                return 0
            pipe = client.pipeline()
            for token_hash in token_hashes:
                pipe.delete(self._rt_key(token_hash))
                pipe.set(self._replay_key(token_hash), family_id, ex=ttl)
            pipe.delete(family_key)
            pipe.execute()
            return len(token_hashes)
        except RedisError as exc:
            raise RefreshSessionError("Could not revoke session family") from exc

    # --- Postgres (legacy) ---

    def _persist_postgres(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        plain: str,
    ) -> AuthRefreshToken:
        expires_at = datetime.now(tz=UTC) + timedelta(days=self._settings.jwt_refresh_token_expire_days)
        row = AuthRefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(plain, settings=self._settings),
            expires_at=expires_at,
        )
        db.add(row)
        db.flush()
        return row

    def _find_valid_postgres(self, db: Session, *, plain: str) -> AuthRefreshToken | None:
        token_hash = hash_refresh_token(plain, settings=self._settings)
        now = datetime.now(tz=UTC)
        return db.scalar(
            select(AuthRefreshToken).where(
                AuthRefreshToken.token_hash == token_hash,
                AuthRefreshToken.revoked_at.is_(None),
                AuthRefreshToken.expires_at > now,
            )
        )

    def _rotate_postgres(
        self,
        db: Session,
        plain: str,
    ) -> tuple[RefreshTokenRecord, str, AuthUser] | None:
        row = self._find_valid_postgres(db, plain=plain)
        if row is None:
            return None
        user = db.get(AuthUser, row.user_id)
        if user is None:
            return None
        if row.revoked_at is None:
            row.revoked_at = datetime.now(tz=UTC)
            db.add(row)
        new_plain = generate_refresh_token_plain()
        self._persist_postgres(db, user_id=user.id, plain=new_plain)
        record = RefreshTokenRecord(user_id=user.id)
        return record, new_plain, user

    def _revoke_plain_postgres(self, db: Session, plain: str) -> bool:
        row = self._find_valid_postgres(db, plain=plain)
        if row is None:
            return False
        if row.revoked_at is None:
            row.revoked_at = datetime.now(tz=UTC)
            db.add(row)
        return True

    def _revoke_all_postgres(self, db: Session, user_id: uuid.UUID) -> int:
        now = datetime.now(tz=UTC)
        rows = db.scalars(
            select(AuthRefreshToken).where(
                AuthRefreshToken.user_id == user_id,
                AuthRefreshToken.revoked_at.is_(None),
            )
        ).all()
        count = 0
        for row in rows:
            row.revoked_at = now
            db.add(row)
            count += 1
        return count


@lru_cache
def get_refresh_session_service() -> RefreshSessionService:
    """Singleton servizio sessioni refresh."""
    return RefreshSessionService()
