import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Job, DeadLetterJob, WebhookConfig
from src.models.job import JobStatus, ChannelType
from src.services.redis_lock import RedisLock


class JobRepository:
    def __init__(self, session: AsyncSession, redis_lock: RedisLock):
        self._session = session
        self._lock = redis_lock


    async def create_job(
        self,
        idempotency_key: str,
        recipient: str,
        channel: ChannelType,
        payload: dict,
        priority: int,
        send_at: datetime,
        max_retries: int = 5,
    ) -> tuple[Job, bool]:

        existing = await self._session.execute(
            select(Job).where(Job.idempotency_key == idempotency_key)
        )
        existing_job = existing.scalar_one_or_none()
        if existing_job is not None:
            return existing_job, False

        job = Job(
            idempotency_key=idempotency_key,
            recipient=recipient,
            channel=channel,
            payload=payload,
            priority=priority,
            send_at=send_at,
            max_retries=max_retries,
            status=JobStatus.PENDING,
            attempt_count=0,
        )
        self._session.add(job)
        await self._session.flush()
        return job, True


    async def claim_next_batch(
        self,
        worker_id: str,
        batch_size: int = 10,
    ) -> list[tuple[Job, str]]:
        
        now = datetime.now(timezone.utc)

        stmt = (
            select(Job)
            .where(
                Job.status == JobStatus.PENDING,
                Job.send_at <= now,
            )
            .order_by(Job.priority.asc(), Job.send_at.asc())
            .limit(batch_size * 3)
        )
        result = await self._session.execute(stmt)
        candidates = list(result.scalars().all())

        claimed: list[tuple[Job, str]] = []

        for job in candidates:
            if len(claimed) >= batch_size:
                break

            token = await self._lock.acquire(
                job_id=str(job.id),
                worker_id=worker_id,
            )
            if token is None:
                continue  

            rows_updated = await self._session.execute(
                update(Job)
                .where(
                    Job.id == job.id,
                    Job.status == JobStatus.PENDING,  
                )
                .values(
                    status=JobStatus.CLAIMED,
                    claimed_by=worker_id,
                    claimed_at=now,
                    attempt_count=Job.attempt_count + 1,
                )
            )

            if rows_updated.rowcount == 1:
                job.status = JobStatus.CLAIMED
                job.claimed_by = worker_id
                job.claimed_at = now
                job.attempt_count += 1
                claimed.append((job, token))
            else:
                await self._lock.release(str(job.id), token)

        return claimed


    async def mark_sent(self, job_id: uuid.UUID) -> Optional[Job]:
        result = await self._session.execute(
            select(Job).where(Job.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None
        job.status = JobStatus.SENT
        job.claimed_by = None
        job.claimed_at = None
        job.updated_at = datetime.now(timezone.utc)
        return job

    async def mark_failed(
        self,
        job_id: uuid.UUID,
        error: str,
        next_retry_at: datetime,
    ) -> Optional[Job]:
        result = await self._session.execute(
            select(Job).where(Job.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None
        job.status = JobStatus.PENDING
        job.claimed_by = None
        job.claimed_at = None
        job.last_error = error
        job.next_retry_at = next_retry_at
        job.send_at = next_retry_at
        job.updated_at = datetime.now(timezone.utc)
        return job

    async def move_to_dead_letter(
        self,
        job_id: uuid.UUID,
        reason: str,
        last_error: str,
    ) -> Optional[DeadLetterJob]:
        result = await self._session.execute(
            select(Job).where(Job.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None
        job.status = JobStatus.DEAD_LETTERED
        job.claimed_by = None
        job.claimed_at = None
        job.last_error = last_error
        job.updated_at = datetime.now(timezone.utc)
        dl_job = DeadLetterJob(
            original_job_id=job_id,
            reason=reason,
            last_error=last_error,
        )
        self._session.add(dl_job)
        await self._session.flush()
        return dl_job

    async def defer_job(
        self,
        job_id: uuid.UUID,
        new_send_at: datetime,
    ) -> Optional[Job]:
        result = await self._session.execute(
            select(Job).where(Job.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None
        job.status = JobStatus.PENDING
        job.claimed_by = None
        job.claimed_at = None
        job.send_at = new_send_at
        job.updated_at = datetime.now(timezone.utc)
        return job


    async def get_by_id(self, job_id: uuid.UUID) -> Optional[Job]:
        result = await self._session.execute(
            select(Job).where(Job.id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_metrics(self) -> dict[str, int]:
        result = await self._session.execute(
            select(
                Job.status,
                func.count(Job.id).label("count"),
            ).group_by(Job.status)
        )
        counts = {row.status.value: row.count for row in result.all()}
        all_statuses = {s.value: 0 for s in JobStatus}
        all_statuses.update(counts)
        all_statuses["total"] = sum(counts.values())
        return all_statuses


    async def recover_stale_claims(
        self,
        stale_threshold: timedelta = timedelta(minutes=5),
    ) -> int:
        cutoff = datetime.now(timezone.utc) - stale_threshold
        result = await self._session.execute(
            update(Job)
            .where(
                Job.status == JobStatus.CLAIMED,
                Job.claimed_at < cutoff,
            )
            .values(
                status=JobStatus.PENDING,
                claimed_by=None,
                claimed_at=None,
            )
        )
        return result.rowcount


    async def create_webhook_config(
        self, url: str, events: list[str],
    ) -> WebhookConfig:
        config = WebhookConfig(url=url, events=events)
        self._session.add(config)
        await self._session.flush()
        return config

    async def get_active_webhooks(self) -> list[WebhookConfig]:
        result = await self._session.execute(
            select(WebhookConfig).where(WebhookConfig.is_active == True)
        )
        return list(result.scalars().all())