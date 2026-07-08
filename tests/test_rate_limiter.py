

import time
import pytest
import pytest_asyncio
import redis.asyncio as aioredis
from datetime import datetime, timezone, timedelta

from src.services.redis_rate_limiter import RedisRateLimiter
from src.core.config import settings


@pytest.mark.asyncio
class TestRedisRateLimiter:

    async def test_sliding_window_rate_limiting(self, test_redis: aioredis.Redis):

        limiter = RedisRateLimiter(test_redis)
        recipient = "rate-limit-test@example.com"
        max_per_window = 3
        window_seconds = 2

        for i in range(max_per_window):
            is_limited, count = await limiter.check_rate_limit(
                recipient, max_per_window=max_per_window, window_seconds=window_seconds
            )
            assert not is_limited
            assert count == i
            await limiter.record_send(recipient, window_seconds=window_seconds)

        is_limited, count = await limiter.check_rate_limit(
            recipient, max_per_window=max_per_window, window_seconds=window_seconds
        )
        assert is_limited
        assert count == 3

        time.sleep(2.1)

        is_limited, count = await limiter.check_rate_limit(
            recipient, max_per_window=max_per_window, window_seconds=window_seconds
        )
        assert not is_limited
        assert count == 0

    async def test_next_available_slot(self, test_redis: aioredis.Redis):
    
        limiter = RedisRateLimiter(test_redis)
        recipient = "slot-test@example.com"
        window_seconds = 60

        now = datetime.now(timezone.utc)
        await limiter.record_send(recipient, window_seconds=window_seconds)

        slot = await limiter.next_available_slot(recipient, window_seconds=window_seconds)
        
        diff = slot - now
        assert 59 <= diff.total_seconds() <= 61
