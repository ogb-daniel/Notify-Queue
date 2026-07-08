
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Job, JobStatus, ChannelType
from src.repositories.job_repository import JobRepository
from src.services.redis_lock import RedisLock


@pytest.mark.asyncio
class TestPriorityOrdering:
    async def test_higher_priority_claimed_first(
        self, session: AsyncSession, redis_lock: RedisLock,
    ):

        now = datetime.now(timezone.utc) - timedelta(minutes=1)

        priorities = [5, 1, 3, 2, 4]
        for p in priorities:
            job = Job(
                idempotency_key=f"priority-test-{p}-{uuid.uuid4().hex[:8]}",
                recipient="priority-user@example.com",
                channel=ChannelType.EMAIL,
                payload={},
                priority=p,
                status=JobStatus.PENDING,
                send_at=now,
                max_retries=5,
            )
            session.add(job)
        await session.flush()

        repo = JobRepository(session, redis_lock)
        claimed = await repo.claim_next_batch("test-worker", batch_size=10)

        claimed_priorities = [j.priority for j, _ in claimed]
        assert claimed_priorities == sorted(claimed_priorities)

    async def test_same_priority_fifo(
        self, session: AsyncSession, redis_lock: RedisLock,
    ):
       
        base_time = datetime.now(timezone.utc) - timedelta(minutes=10)

        for i in range(5):
            job = Job(
                idempotency_key=f"fifo-test-{i}-{uuid.uuid4().hex[:8]}",
                recipient="fifo-user@example.com",
                channel=ChannelType.EMAIL,
                payload={"order": i},
                priority=3,
                status=JobStatus.PENDING,
                send_at=base_time + timedelta(seconds=i),
                max_retries=5,
            )
            session.add(job)
        await session.flush()

        repo = JobRepository(session, redis_lock)
        claimed = await repo.claim_next_batch("test-worker", batch_size=10)

        send_times = [j.send_at for j, _ in claimed if j.priority == 3]
        assert send_times == sorted(send_times)
