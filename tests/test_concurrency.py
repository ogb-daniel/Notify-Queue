
import asyncio
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models import Job, JobStatus, ChannelType
from src.repositories.job_repository import JobRepository
from src.services.redis_lock import RedisLock


@pytest.mark.asyncio
class TestConcurrentWorkers:

    async def test_no_duplicate_delivery(
        self,
        session_factory: async_sessionmaker,
        redis_lock: RedisLock,
    ):
  
        num_jobs = 50
        num_workers = 10
        now = datetime.now(timezone.utc) - timedelta(minutes=1)

        async with session_factory() as setup_session:
            for i in range(num_jobs):
                job = Job(
                    idempotency_key=f"concurrency-test-{uuid.uuid4().hex}",
                    recipient=f"user{i}@example.com",
                    channel=ChannelType.EMAIL,
                    payload={"index": i},
                    priority=3,
                    status=JobStatus.PENDING,
                    send_at=now,
                    max_retries=5,
                )
                setup_session.add(job)
            await setup_session.commit()

        claimed_by_worker: dict[str, list[uuid.UUID]] = {}

        async def worker_claim(worker_id: str) -> list[uuid.UUID]:
            claimed_ids = []
            while True:
                async with session_factory() as worker_session:
                    repo = JobRepository(worker_session, redis_lock)
                    batch = await repo.claim_next_batch(
                        worker_id=worker_id,
                        batch_size=5,
                    )
                    await worker_session.commit()

                    if not batch:
                        break

                    claimed_ids.extend(job.id for job, _ in batch)
            return claimed_ids

        tasks = [
            worker_claim(f"worker-{i}")
            for i in range(num_workers)
        ]
        results = await asyncio.gather(*tasks)

        all_claimed_ids = []
        for i, worker_ids in enumerate(results):
            worker_name = f"worker-{i}"
            claimed_by_worker[worker_name] = worker_ids
            all_claimed_ids.extend(worker_ids)


        id_counts = Counter(all_claimed_ids)
        duplicates = {
            str(jid): count
            for jid, count in id_counts.items()
            if count > 1
        }
        assert len(duplicates) == 0, (
            f"DUPLICATE DELIVERY DETECTED! "
            f"Jobs claimed multiple times: {duplicates}"
        )

        assert len(all_claimed_ids) == num_jobs, (
            f"MISSED JOBS! Expected {num_jobs}, got {len(all_claimed_ids)}"
        )

        active_workers = sum(
            1 for ids in claimed_by_worker.values() if len(ids) > 0
        )
        assert active_workers > 1, (
            "Only 1 worker got jobs - concurrency wasn't actually tested"
        )

    async def test_claimed_jobs_not_visible_to_other_workers(
        self,
        session_factory: async_sessionmaker,
        redis_lock: RedisLock,
    ):

        now = datetime.now(timezone.utc) - timedelta(minutes=1)

        async with session_factory() as session:
            job = Job(
                idempotency_key=f"visibility-test-{uuid.uuid4().hex}",
                recipient="visibility-user@example.com",
                channel=ChannelType.EMAIL,
                payload={},
                priority=1,
                status=JobStatus.PENDING,
                send_at=now,
                max_retries=5,
            )
            session.add(job)
            await session.commit()

        results = await asyncio.gather(
            self._claim_all(session_factory, redis_lock, "worker-a"),
            self._claim_all(session_factory, redis_lock, "worker-b"),
        )

        total_claimed = sum(len(r) for r in results)
        assert total_claimed == 1, (
            f"Job was claimed {total_claimed} times - expected exactly 1"
        )

    @staticmethod
    async def _claim_all(
        session_factory: async_sessionmaker,
        redis_lock: RedisLock,
        worker_id: str,
    ) -> list:
        async with session_factory() as session:
            repo = JobRepository(session, redis_lock)
            jobs = await repo.claim_next_batch(worker_id, batch_size=10)
            await session.commit()
            return jobs
