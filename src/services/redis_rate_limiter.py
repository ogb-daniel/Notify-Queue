import time
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import redis.asyncio as redis
from src.core.config import settings
logger = logging.getLogger(__name__)

class RedisRateLimiter:
    def __init__(self, client: redis.Redis):
        self._client = client
        self._settings = get_settings()
        
    def _key(self, recipient: str) -> str:
        return f"{self._settings.REDIS_RATE_LIMIT_PREFIX}{recipient}"
   
    async def check_rate_limit(
        self,
        recipient: str,
        max_per_window: int | None = None,
        window_seconds: int | None = None,
    ) -> tuple[bool, int]:
       
        if max_per_window is None:
            max_per_window = self._settings.RATE_LIMIT_PER_RECIPIENT_PER_HOUR
        if window_seconds is None:
            window_seconds = self._settings.RATE_LIMIT_WINDOW_SECONDS
        key = self._key(recipient)
        now = time.time()
        window_start = now - window_seconds
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            results = await pipe.execute()
        current_count = results[1] 
        is_limited = current_count >= max_per_window
        if is_limited:
            logger.debug(
                "Rate limited: recipient=%s count=%d/%d",
                recipient, current_count, max_per_window,
            )
        return is_limited, current_count

    async def record_send(
        self,
        recipient: str,
        window_seconds: int | None = None,
    ) -> None:

        if window_seconds is None:
            window_seconds = self._settings.RATE_LIMIT_WINDOW_SECONDS
        key = self._key(recipient)
        now = time.time()
        member = f"{now}:{uuid.uuid4().hex[:8]}"
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.zadd(key, {member: now})
           
            pipe.expire(key, window_seconds + 60)
            await pipe.execute()
    
    async def next_available_slot(
        self,
        recipient: str,
        window_seconds: int | None = None,
    ) -> datetime:
        if window_seconds is None:
            window_seconds = self._settings.RATE_LIMIT_WINDOW_SECONDS
        key = self._key(recipient)
        oldest = await self._client.zrange(
            key, 0, 0, withscores=True,
        )
        if oldest:
            oldest_timestamp = oldest[0][1] 
            next_slot = oldest_timestamp + window_seconds
            return datetime.fromtimestamp(next_slot, tz=timezone.utc)
        return datetime.now(timezone.utc)