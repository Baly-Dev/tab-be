"""Client Redis sync (script/legacy) e async (API FastAPI)."""

from __future__ import annotations

import logging
from functools import lru_cache

from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import RedisError

from config import Settings, get_settings

logger = logging.getLogger(__name__)


class RedisService:
    """Lifecycle e client **sync** (test, script). Preferire ``get_async_redis_service`` in API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: Redis | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self._settings.redis_url.strip())

    def connect(self) -> None:
        if self._client is not None:
            return
        url = self._settings.redis_url.strip()
        if not url:
            raise ValueError("REDIS_URL is not configured")
        self._client = Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        self._client.ping()
        logger.info("Redis (sync) connected")

    def close(self) -> None:
        if self._client is None:
            return
        try:
            self._client.close()
        except RedisError:
            logger.exception("Error closing sync Redis client")
        self._client = None

    def get_client(self) -> Redis:
        if self._client is None:
            self.connect()
        assert self._client is not None
        return self._client

    def ping(self) -> bool:
        if not self.is_configured:
            return False
        try:
            if self._client is None:
                self.connect()
            assert self._client is not None
            return bool(self._client.ping())
        except RedisError:
            logger.warning("Redis sync ping failed", exc_info=True)
            return False


class AsyncRedisService:
    """Client **async** per route, refresh e rate limit (repliche Railway condividono REDIS_URL)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: AsyncRedis | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self._settings.redis_url.strip())

    async def connect(self) -> None:
        if self._client is not None:
            return
        url = self._settings.redis_url.strip()
        if not url:
            raise ValueError("REDIS_URL is not configured")
        self._client = AsyncRedis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        await self._client.ping()
        logger.info("Redis (async) connected")

    async def close(self) -> None:
        if self._client is None:
            return
        try:
            await self._client.aclose()
        except RedisError:
            logger.exception("Error closing async Redis client")
        self._client = None

    def get_client(self) -> AsyncRedis:
        if self._client is None:
            raise RuntimeError("Async Redis is not connected; await connect() in app lifespan")
        return self._client

    async def ping(self) -> bool:
        if not self.is_configured:
            return False
        try:
            if self._client is None:
                await self.connect()
            assert self._client is not None
            return bool(await self._client.ping())
        except RedisError:
            logger.warning("Redis async ping failed", exc_info=True)
            return False


@lru_cache
def get_redis_service() -> RedisService:
    return RedisService()


@lru_cache
def get_async_redis_service() -> AsyncRedisService:
    return AsyncRedisService()