import json, logging
import redis.asyncio as aioredis
import redis
from typing import Any

from src.shared.config import settings

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self):
        self.redis: aioredis.Redis | None = None
        self.sync_redis: redis.Redis | None = None

    async def connect(self):
        if not self.redis:
            self.redis = aioredis.from_url(str(settings.REDIS_URL), decode_responses=True)
            await self.redis.ping()
            self.sync_redis = redis.from_url(str(settings.REDIS_URL), decode_responses=True)
            logger.info("✅ Redis connected")

    async def disconnect(self):
        if self.redis:
            await self.redis.close()

    # ——— Обёртки ———
    async def set(self, key: str, value: Any, ex: int | None = None):
        await self.redis.set(key, json.dumps(value, default=str), ex=ex)

    async def get(self, key: str):
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    async def lpush(self, key: str, value: Any):
        await self.redis.lpush(key, json.dumps(value, default=str))

    async def increment_counter(self, key: str):
        return await self.redis.incr(key)

    async def expire(self, key: str, ttl: int):
        await self.redis.expire(key, ttl)

    # Очереди генерации
    async def add_to_generation_queue(self, task: dict, priority=False):
        q = "priority_queue" if priority else "generation_queue"
        await self.lpush(q, task)

    async def get_queue_length(self, queue: str):
        return await self.redis.llen(queue)

    async def clear_generation_queues(self):
        await self.redis.delete("priority_queue", "generation_queue", "processing")

    async def get_statistics(self):
        info = await self.redis.info()
        return {
            "connected": True,
            "memory_usage_mb": round(info["Memory"]["used_memory"] / 1_048_576, 1),
            "connected_clients": info["Clients"]["connected_clients"],
        }

redis_client = RedisClient()
