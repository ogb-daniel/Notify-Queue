from src.core.config import settings
import redis.asyncio as redis

async def init_redis() -> redis.Redis:
    global _redis_pool
    _redis_pool = redis.from_url(
        f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0", encoding="utf-8", decode_responses=True
    )
    return _redis_pool


async def close_redis() -> None:
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None

def get_redis() -> redis.Redis:
    if _redis_pool is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_pool