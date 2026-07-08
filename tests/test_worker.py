

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models import Job, JobStatus, ChannelType, DeadLetterJob
from src.repositories.job_repository import JobRepository
from src.services.redis_lock import RedisLock
from src.services.redis_rate_limiter import RedisRateLimiter
from src.services.worker_service import _process_single_job
from src.senders.base import NotificationSender, SentReceipt, SendError
from src.domain.result import Ok, Err, Result


class MockSender(NotificationSender):
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.calls = 0

    async def send(self, job_id: str, recipient: str, payload: dict) -> Result:
        self.calls += 1
        if self.should_fail:
            return Err(SendError("Mock failure"))
        return Ok(SentReceipt(delivered_at=datetime.now(timezone.utc), provider_message_id="mock-id"))


@pytest.mark.asyncio
class TestWorkerService:

    async def test_job_deferred_when_rate_limited(
        self, session: AsyncSession, redis_lock: RedisLock, test_redis
    ):
        repo = JobRepository(session, redis_lock)
        rate_limiter = RedisRateLimiter(test_redis)
        sender = MockSender(should_fail=False)

        job, _ = await repo.create_job(
            idempotency_key=f"defer-{uuid.uuid4()}",
            recipient="defer@example.com",
            channel=ChannelType.EMAIL,
            payload={},
            priority=3,
            send_at=datetime.now(timezone.utc),
        )
        job.status = JobStatus.CLAIMED
        await session.commit()

        for _ in range(10):
            await rate_limiter.record_send(job.recipient)

        await _process_single_job(
            job, "mock-token", repo, session, redis_lock, rate_limiter, sender
        )
        await session.commit()

        updated_job = await repo.get_by_id(job.id)
        assert updated_job.status == JobStatus.PENDING
        assert updated_job.send_at > datetime.now(timezone.utc)
        assert sender.calls == 0

    async def test_job_retried_with_backoff_on_failure(
        self, session: AsyncSession, redis_lock: RedisLock, test_redis
    ):
        repo = JobRepository(session, redis_lock)
        rate_limiter = RedisRateLimiter(test_redis)
        sender = MockSender(should_fail=True) 

        job, _ = await repo.create_job(
            idempotency_key=f"retry-{uuid.uuid4()}",
            recipient="retry@example.com",
            channel=ChannelType.EMAIL,
            payload={},
            priority=3,
            send_at=datetime.now(timezone.utc),
            max_retries=5,
        )
        job.status = JobStatus.CLAIMED
        job.attempt_count = 1
        await session.commit()

        await _process_single_job(
            job, "mock-token", repo, session, redis_lock, rate_limiter, sender
        )
        await session.commit()

        updated_job = await repo.get_by_id(job.id)
        assert updated_job.status == JobStatus.PENDING
        assert updated_job.attempt_count == 1
        assert updated_job.last_error == "Mock failure"
        assert updated_job.send_at > datetime.now(timezone.utc)
        assert sender.calls == 1

    async def test_job_dead_lettered_after_max_retries(
        self, session: AsyncSession, redis_lock: RedisLock, test_redis
    ):
        repo = JobRepository(session, redis_lock)
        rate_limiter = RedisRateLimiter(test_redis)
        sender = MockSender(should_fail=True)

        job, _ = await repo.create_job(
            idempotency_key=f"dlq-{uuid.uuid4()}",
            recipient="dlq@example.com",
            channel=ChannelType.EMAIL,
            payload={},
            priority=3,
            send_at=datetime.now(timezone.utc),
            max_retries=3,
        )
        job.status = JobStatus.CLAIMED
        job.attempt_count = 3  
        await session.commit()

        await _process_single_job(
            job, "mock-token", repo, session, redis_lock, rate_limiter, sender
        )
        await session.commit()

        updated_job = await repo.get_by_id(job.id)
        assert updated_job.status == JobStatus.DEAD_LETTERED
        
        dlq_result = await session.execute(
            select(DeadLetterJob).where(DeadLetterJob.original_job_id == job.id)
        )
        dlq_entry = dlq_result.scalar_one_or_none()
        assert dlq_entry is not None
        assert dlq_entry.last_error == "Mock failure"
        assert dlq_entry.reason == "Exhausted 3 retries"
