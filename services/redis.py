"""Client Redis: connessione, healthcheck e accesso centralizzato."""

from __future__ import annotations

import logging
from functools import lru_cache

from redis import Redis
from redis.exceptions import RedisError

from config import Settings, get_settings

logger = logging.getLogger(__name__)


class RedisService:
    """Collo di bottiglia configurazione e lifecycle client Redis."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: Redis | None = None

    @property
    def is_configured(self) -> bool:
        """True se ``REDIS_URL`` è valorizzato."""
        return bool(self._settings.redis_url.strip())

    def connect(self) -> None:
        """Apre il client (idempotente)."""
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
        logger.info("Redis connected")

    def close(self) -> None:
        """Chiude il client."""
        if self._client is None:
            return
        try:
            self._client.close()
        except RedisError:
            logger.exception("Error closing Redis client")
        self._client = None

    def get_client(self) -> Redis:
        """Client attivo; ``connect()`` se necessario."""
        if self._client is None:
            self.connect()
        assert self._client is not None
        return self._client

    def ping(self) -> bool:
        """Healthcheck; False se non configurato o non raggiungibile."""
        if not self.is_configured:
            return False
        try:
            if self._client is None:
                self.connect()
            assert self._client is not None
            return bool(self._client.ping())
        except RedisError:
            logger.warning("Redis ping failed", exc_info=True)
            return False


@lru_cache
def get_redis_service() -> RedisService:
    """Dependency / singleton applicazione."""
    return RedisService()
