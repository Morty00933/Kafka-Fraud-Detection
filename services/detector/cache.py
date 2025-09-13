from __future__ import annotations
import asyncio
from typing import Optional
import redis.asyncio as redis

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

    async def set_flag(self, tx_id: str, ttl_sec: int = 24*3600):
        await self._client.setex(f"{self._prefix}:{tx_id}", ttl_sec, "1")

    async def is_flagged(self, tx_id: str) -> bool:
        v = await self._client.get(f"{self._prefix}:{tx_id}")
        return v is not None

    # для корректного закрытия при завершении event loop
    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
        await asyncio.sleep(0)  # дать шанс flush'у
