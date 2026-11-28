"""Sessioni refresh: store Redis (default) o fallback Postgres."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models.refresh_token import AuthRefreshToken
from auth.models.user import AuthUser
from auth.utils.tokens import generate_refresh_token_plain, hash_refresh_token
from config import Settings, get_settings
from services.redis import AsyncRedisService, get_async_redis_service

logger = logging.getLogger(__name__)

KEY_PREFIX = "tn"
REPLAY_KEY_PREFIX = f"{KEY_PREFIX}:rt_replay"
GRACE_KEY_PREFIX = f"{KEY_PREFIX}:rt_grace"
FAMILY_KEY_PREFIX = f"{KEY_PREFIX}:family:"

# Consume the current hash, write the successor, mark replay. One round-trip.
_ROTATE_LUA = """
local old_key = KEYS[1]
local replay_key = KEYS[2]
local new_key = KEYS[3]
local grace_key = KEYS[4]
local ttl = tonumber(ARGV[1])
local grace = tonumber(ARGV[2])
local old_hash = ARGV[3]
local new_hash = ARGV[4]
local new_plain = ARGV[5]
local family_prefix = ARGV[6]

local data = redis.call('HGETALL', old_key)
if #data == 0 then
  return {}
end

local user_id = false
local family_id = false
for i = 1, #data, 2 do
  local field = data[i]
  local value = data[i + 1]
  if field == 'user_id' then
    user_id = value
  elseif field == 'family_id' then
    family_id = value
  end
end

if (not user_id) or (not family_id) then
  redis.call('DEL', old_key)
  return {}
end

local family_key = family_prefix .. family_id .. ':tokens'
redis.call('DEL', old_key)
redis.call('SET', replay_key, family_id, 'EX', ttl)
redis.call('SREM', family_key, old_hash)
redis.call('HSET', new_key, 'user_id', user_id, 'family_id', family_id)
redis.call('EXPIRE', new_key, ttl)
redis.call('SADD', family_key, new_hash)
redis.call('EXPIRE', family_key, ttl)
if grace > 0 then
  redis.call('SET', grace_key, new_plain .. '\\n' .. user_id .. '\\n' .. family_id, 'EX', grace)
end
return {user_id, family_id}
"""

# Delete the current hash and mark replay so a concurrent rotate cannot reissue it.
_CONSUME_LUA = """
local rt_key = KEYS[1]
local replay_key = KEYS[2]
local ttl = tonumber(ARGV[1])
local old_hash = ARGV[2]
local family_prefix = ARGV[3]

local data = redis.call('HGETALL', rt_key)
if #data == 0 then
  return {}
end

local user_id = false
local family_id = false
for i = 1, #data, 2 do
  if data[i] == 'user_id' then
    user_id = data[i + 1]
  elseif data[i] == 'family_id' then
    family_id = data[i + 1]
  end
end

redis.call('DEL', rt_key)
if family_id then
  redis.call('SET', replay_key, family_id, 'EX', ttl)
  redis.call('SREM', family_prefix .. family_id .. ':tokens', old_hash)
end
if (not user_id) or (not family_id) then
  return {}
end
return {user_id, family_id}
"""


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
        redis: AsyncRedisService | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._redis = redis or get_async_redis_service()

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

    def _grace_key(self, token_hash: str) -> str:
        return f"{GRACE_KEY_PREFIX}:{token_hash}"

    async def persist(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        plain: str,
    ) -> RefreshTokenRecord:
        """Registra un nuovo refresh (nuova famiglia sessione)."""
        if self.uses_redis:
            family_id = await self._persist_redis(user_id=user_id, plain=plain)
            return RefreshTokenRecord(user_id=user_id, family_id=family_id)
        row = await self._persist_postgres(db, user_id=user_id, plain=plain)
        return RefreshTokenRecord(user_id=row.user_id)

    async def find_valid(self, db: AsyncSession, *, plain: str) -> RefreshTokenRecord | None:
        """Refresh attivo per token plain, se esiste."""
        if self.uses_redis:
            return await self._find_valid_redis(plain=plain)
        row = await self._find_valid_postgres(db, plain=plain)
        if row is None:
            return None
        return RefreshTokenRecord(user_id=row.user_id)

    async def rotate(
        self,
        db: AsyncSession,
        plain: str,
    ) -> tuple[RefreshTokenRecord, str, AuthUser] | None:
        """Ruota refresh; None se invalido. Rileva riuso (revoca famiglia)."""
        if self.uses_redis:
            return await self._rotate_redis(db, plain=plain)
        return await self._rotate_postgres(db, plain=plain)

    async def revoke_plain(self, db: AsyncSession, plain: str) -> bool:
        """Revoca un singolo refresh."""
        if self.uses_redis:
            return await self._revoke_plain_redis(plain=plain)
        return await self._revoke_plain_postgres(db, plain=plain)

    async def revoke_all_for_user(self, db: AsyncSession, user_id: uuid.UUID) -> int:
        """Revoca tutte le sessioni refresh dell'utente."""
        if self.uses_redis:
            return await self._revoke_all_redis(user_id=user_id)
        return await self._revoke_all_postgres(db, user_id=user_id)

    # --- Redis ---

    async def _persist_redis(self, *, user_id: uuid.UUID, plain: str) -> str:
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
            await pipe.execute()
        except RedisError as exc:
            raise RefreshSessionError("Could not persist refresh session") from exc
        return family_id

    async def _find_valid_redis(self, *, plain: str) -> RefreshTokenRecord | None:
        token_hash = hash_refresh_token(plain, settings=self._settings)
        client = self._redis.get_client()
        try:
            data = await client.hgetall(self._rt_key(token_hash))
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

    async def _rotate_redis(
        self,
        db: AsyncSession,
        *,
        plain: str,
    ) -> tuple[RefreshTokenRecord, str, AuthUser] | None:
        token_hash = hash_refresh_token(plain, settings=self._settings)
        client = self._redis.get_client()
        new_plain = generate_refresh_token_plain()
        new_hash = hash_refresh_token(new_plain, settings=self._settings)
        ttl = self._ttl_seconds()
        grace = max(0, int(self._settings.refresh_rotation_grace_seconds))
        try:
            swapped = await client.eval(
                _ROTATE_LUA,
                4,
                self._rt_key(token_hash),
                self._replay_key(token_hash),
                self._rt_key(new_hash),
                self._grace_key(token_hash),
                ttl,
                grace,
                token_hash,
                new_hash,
                new_plain,
                FAMILY_KEY_PREFIX,
            )
        except RedisError as exc:
            raise RefreshSessionError("Could not rotate refresh session") from exc

        parsed = self._user_family_from_eval(swapped)
        if parsed is not None:
            user_id, family_id = parsed
            return await self._loaded_rotation(
                db, user_id=user_id, family_id=family_id, new_plain=new_plain
            )

        reused = await self._grace_rotation(db, client, token_hash=token_hash)
        if reused is not None:
            return reused

        try:
            replay_family = await client.get(self._replay_key(token_hash))
        except RedisError as exc:
            raise RefreshSessionError("Could not rotate refresh session") from exc
        if replay_family:
            logger.warning("Refresh token reuse detected for family %s", replay_family)
            await self._revoke_family_redis(family_id=str(replay_family))
        return None

    async def _revoke_plain_redis(self, *, plain: str) -> bool:
        token_hash = hash_refresh_token(plain, settings=self._settings)
        client = self._redis.get_client()
        try:
            consumed = await client.eval(
                _CONSUME_LUA,
                2,
                self._rt_key(token_hash),
                self._replay_key(token_hash),
                self._ttl_seconds(),
                token_hash,
                FAMILY_KEY_PREFIX,
            )
        except RedisError as exc:
            raise RefreshSessionError("Could not revoke refresh session") from exc
        return self._user_family_from_eval(consumed) is not None

    async def _loaded_rotation(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        family_id: str,
        new_plain: str,
    ) -> tuple[RefreshTokenRecord, str, AuthUser] | None:
        user = await db.get(AuthUser, user_id)
        if user is None:
            await self._revoke_family_redis(family_id=family_id)
            return None
        return RefreshTokenRecord(user_id=user_id, family_id=family_id), new_plain, user

    async def _grace_rotation(
        self,
        db: AsyncSession,
        client,
        *,
        token_hash: str,
    ) -> tuple[RefreshTokenRecord, str, AuthUser] | None:
        try:
            raw = await client.get(self._grace_key(token_hash))
        except RedisError as exc:
            raise RefreshSessionError("Could not rotate refresh session") from exc
        if not raw:
            return None
        parts = str(raw).split("\n")
        if len(parts) != 3:
            return None
        new_plain, user_raw, family_id = parts
        try:
            user_id = uuid.UUID(user_raw)
        except ValueError:
            return None
        if not new_plain or not family_id:
            return None
        return await self._loaded_rotation(db, user_id=user_id, family_id=family_id, new_plain=new_plain)

    @staticmethod
    def _user_family_from_eval(payload: object) -> tuple[uuid.UUID, str] | None:
        if not payload or not isinstance(payload, (list, tuple)) or len(payload) < 2:
            return None
        try:
            return uuid.UUID(str(payload[0])), str(payload[1])
        except ValueError:
            return None

    async def _revoke_all_redis(self, *, user_id: uuid.UUID) -> int:
        client = self._redis.get_client()
        families_key = self._user_families_key(user_id)
        try:
            families = list(await client.smembers(families_key))
            count = 0
            for family_id in families:
                count += await self._revoke_family_redis(family_id=family_id)
            await client.delete(families_key)
        except RedisError as exc:
            raise RefreshSessionError("Could not revoke user sessions") from exc
        return count

    async def _revoke_family_redis(self, *, family_id: str) -> int:
        client = self._redis.get_client()
        family_key = self._family_tokens_key(family_id)
        ttl = self._ttl_seconds()
        try:
            token_hashes = list(await client.smembers(family_key))
            if not token_hashes:
                return 0
            pipe = client.pipeline()
            for token_hash in token_hashes:
                pipe.delete(self._rt_key(token_hash))
                pipe.set(self._replay_key(token_hash), family_id, ex=ttl)
            pipe.delete(family_key)
            await pipe.execute()
            return len(token_hashes)
        except RedisError as exc:
            raise RefreshSessionError("Could not revoke session family") from exc

    # --- Postgres (legacy) ---

    async def _persist_postgres(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        plain: str,
    ) -> AuthRefreshToken:
        expires_at = datetime.now(tz=UTC) + timedelta(
            days=self._settings.jwt_refresh_token_expire_days
        )
        row = AuthRefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(plain, settings=self._settings),
            expires_at=expires_at,
        )
        db.add(row)
        await db.flush()
        return row

    async def _find_valid_postgres(self, db: AsyncSession, *, plain: str) -> AuthRefreshToken | None:
        token_hash = hash_refresh_token(plain, settings=self._settings)
        now = datetime.now(tz=UTC)
        return await db.scalar(
            select(AuthRefreshToken).where(
                AuthRefreshToken.token_hash == token_hash,
                AuthRefreshToken.revoked_at.is_(None),
                AuthRefreshToken.expires_at > now,
            )
        )

    async def _rotate_postgres(
        self,
        db: AsyncSession,
        plain: str,
    ) -> tuple[RefreshTokenRecord, str, AuthUser] | None:
        token_hash = hash_refresh_token(plain, settings=self._settings)
        now = datetime.now(tz=UTC)
        row = await db.scalar(
            select(AuthRefreshToken)
            .where(AuthRefreshToken.token_hash == token_hash)
            .with_for_update()
        )
        if row is None or not row.is_valid_at(now):
            return None
        user = await db.get(AuthUser, row.user_id)
        if user is None:
            row.revoke(now)
            db.add(row)
            return None
        row.revoke(now)
        db.add(row)
        new_plain = generate_refresh_token_plain()
        await self._persist_postgres(db, user_id=user.id, plain=new_plain)
        record = RefreshTokenRecord(user_id=user.id)
        return record, new_plain, user

    async def _revoke_plain_postgres(self, db: AsyncSession, plain: str) -> bool:
        row = await self._find_valid_postgres(db, plain=plain)
        if row is None:
            return False
        row.revoke(datetime.now(tz=UTC))
        db.add(row)
        return True

    async def _revoke_all_postgres(self, db: AsyncSession, user_id: uuid.UUID) -> int:
        now = datetime.now(tz=UTC)
        rows = (
            await db.scalars(
                select(AuthRefreshToken).where(
                    AuthRefreshToken.user_id == user_id,
                    AuthRefreshToken.revoked_at.is_(None),
                )
            )
        ).all()
        count = 0
        for row in rows:
            row.revoke(now)
            db.add(row)
            count += 1
        return count


@lru_cache
def get_refresh_session_service() -> RefreshSessionService:
    """Singleton servizio sessioni refresh."""
    return RefreshSessionService()