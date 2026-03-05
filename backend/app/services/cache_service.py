# backend/app/services/cache_service.py

import json
from typing import Any, Optional
import redis.asyncio as redis

from app.core.config import settings


class CacheService:
    def __init__(self) -> None:
        self.client: redis.Redis = redis.from_url(
            settings.REDIS_URL,
            decode_responses=False
        )

    async def get(self, key: str) -> Optional[Any]:
        value: Optional[bytes] = await self.client.get(key)

        if value is None:
            return None

        return json.loads(value.decode("utf-8"))

    async def set(
        self,
        key: str,
        data: Any,
        expire: Optional[int] = None
    ) -> bool:
        serialized = json.dumps(data).encode("utf-8")

        if expire is not None:
            return await self.client.set(key, serialized, ex=expire)

        return await self.client.set(key, serialized)

    async def delete(self, key: str) -> int:
        return await self.client.delete(key)


cache_service = CacheService()