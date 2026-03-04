from __future__ import annotations
import asyncio
import logging
from typing import Optional
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self, host: str = "redis", port: int = 6379, db: int = 0, prefix: str = "fraud"):
        self._client: Optional[redis.Redis] = None
        self._host, self._port, self._db, self._prefix = host, port, db, prefix

    async def connect(self):
        if self._client is None:
            self._client = redis.Redis(host=self._host, port=self._port, db=self._db, decode_responses=True)

    async def close(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _ensure_connected(self) -> redis.Redis:
        """Ensure client exists, reconnect if needed."""
        if self._client is None:
            logger.warning("Redis client not connected, reconnecting...")
            await self.connect()
        return self._client  # type: ignore[return-value]

    async def set_flag(self, tx_id: str, ttl_sec: int = 24 * 3600) -> None:
        try:
            client = await self._ensure_connected()
            await client.setex(f"{self._prefix}:{tx_id}", ttl_sec, "1")
        except Exception as exc:
            logger.error("Redis set_flag failed for tx_id=%s: %s", tx_id, exc)

    async def is_flagged(self, tx_id: str) -> bool:
        try:
            client = await self._ensure_connected()
            v = await client.get(f"{self._prefix}:{tx_id}")
            return v is not None
        except Exception as exc:
            logger.error("Redis is_flagged failed for tx_id=%s: %s", tx_id, exc)
            return False

    async def ping(self) -> bool:
        """Health check for Redis."""
        try:
            client = await self._ensure_connected()
            return await client.ping()
        except Exception:
            return False

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
        await asyncio.sleep(0)
