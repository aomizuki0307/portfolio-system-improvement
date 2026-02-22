import json
import logging

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Cache-aside manager backed by Redis.

    All public methods are safe to call even when Redis is unavailable:
    read operations return None and write operations are silently skipped,
    so the application degrades gracefully without raising exceptions to
    callers.
    """

    def __init__(self) -> None:
        self._redis: redis.Redis | None = None
        self._hits: int = 0
        self._misses: int = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open the connection pool.  Called once at application startup."""
        self._redis = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        # Ping to surface mis-configuration early (non-fatal).
        try:
            await self._redis.ping()
            logger.info("Redis connected: %s", settings.REDIS_URL)
        except Exception as exc:  # pragma: no cover
            logger.warning("Redis ping failed — cache disabled: %s", exc)

    async def disconnect(self) -> None:
        """Close the connection pool.  Called once at application shutdown."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    # ------------------------------------------------------------------
    # Core cache operations
    # ------------------------------------------------------------------

    async def get(self, key: str) -> dict | list | None:
        """
        Return the cached value for *key*, or None on a miss / error.

        Increments hit/miss counters for observability.
        """
        if not self._redis:
            self._misses += 1
            return None
        try:
            data = await self._redis.get(key)
            if data is not None:
                self._hits += 1
                return json.loads(data)
            self._misses += 1
            return None
        except Exception as exc:
            logger.debug("Cache GET error for key=%r: %s", key, exc)
            self._misses += 1
            return None

    async def set(self, key: str, value: dict | list, ttl: int | None = None) -> None:
        """
        Persist *value* under *key* with an optional TTL (seconds).

        Serialisation errors and Redis failures are logged but never
        propagated — a cache write failure must never break a request.
        """
        if not self._redis:
            return
        try:
            serialised = json.dumps(value, default=str)
            await self._redis.set(key, serialised, ex=ttl)
        except Exception as exc:
            logger.debug("Cache SET error for key=%r: %s", key, exc)

    async def delete_pattern(self, pattern: str) -> None:
        """
        Delete all keys matching *pattern* using SCAN (avoids blocking KEYS).
        """
        if not self._redis:
            return
        try:
            keys: list[str] = []
            async for key in self._redis.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                await self._redis.delete(*keys)
                logger.debug("Cache invalidated %d key(s) matching %r", len(keys), pattern)
        except Exception as exc:
            logger.debug("Cache DELETE_PATTERN error for pattern=%r: %s", pattern, exc)

    # ------------------------------------------------------------------
    # Domain-level invalidation helpers
    # ------------------------------------------------------------------

    async def invalidate_article(self, article_id: int | None = None) -> None:
        """
        Invalidate article-related caches on any write operation.

        Always purges the list cache (pagination is stale after any
        create/update/delete).  When *article_id* is provided the
        detail entry for that specific article is also removed.
        """
        await self.delete_pattern("articles:list:*")
        if article_id is not None:
            await self.delete_pattern(f"articles:detail:{article_id}")

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict:
        """Return a snapshot of hit/miss counters for metrics endpoints."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total * 100, 1) if total > 0 else 0.0,
        }


# Module-level singleton shared across all request handlers.
cache = CacheManager()
