import uuid
import logging
from typing import Optional
import redis.asyncio as redis
from src.core.config import settings
logger = logging.getLogger(__name__)

class RedisLock:
    RELEASE_SCRIPT = """
    if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("DEL", KEYS[1])
    else
        return 0
    end
    """
    def __init__(self, client: redis.Redis):
        self._client = client
        self._settings = settings
        
    async def acquire(
        self,
        job_id: str,
        worker_id: str,
        timeout_seconds: int | None = None,
    ) -> Optional[str]:
      
        if timeout_seconds is None:
            timeout_seconds = self._settings.REDIS_LOCK_TIMEOUT_SECONDS
        lock_key = f"{self._settings.REDIS_LOCK_PREFIX}{job_id}"
        lock_token = f"{worker_id}:{uuid.uuid4().hex[:8]}"
        acquired = await self._client.set(
            lock_key,
            lock_token,
            nx=True,   
            ex=timeout_seconds,  
        )
        if acquired:
            logger.debug(
                "Lock acquired: job=%s worker=%s token=%s ttl=%ds",
                job_id, worker_id, lock_token, timeout_seconds,
            )
            return lock_token
        logger.debug("Lock denied: job=%s (held by another worker)", job_id)
        return None

    async def release(self, job_id: str, token: str) -> bool:
        lock_key = f"{self._settings.REDIS_LOCK_PREFIX}{job_id}"
        result = await self._client.eval(
            self.RELEASE_SCRIPT,
            1,        
            lock_key,
            token,
        )
        released = result == 1
        if released:
            logger.debug("Lock released: job=%s", job_id)
        else:
            logger.warning(
                "Lock release skipped (not owner): job=%s token=%s",
                job_id, token,
            )
        return released

    async def is_locked(self, job_id: str) -> bool:
        lock_key = f"{self._settings.REDIS_LOCK_PREFIX}{job_id}"
        return await self._client.exists(lock_key) > 0
