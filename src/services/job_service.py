
import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Job, JobStatus
from src.repositories.job_repository import JobRepository
from src.schemas import (
    CreateJobRequest,
    JobResponse,
    JobStatusResponse,
    MetricsResponse,
)
from src.domain.result import Ok, Err, Result

logger = logging.getLogger(__name__)


class JobService:

    def __init__(self, session: AsyncSession):
        self._repo = JobRepository(session)

    async def schedule_job(
        self,
        request: CreateJobRequest,
    ) -> Result:
        try:
            job, created = await self._repo.create_job(
                idempotency_key=request.idempotency_key,
                recipient=request.recipient,
                channel=request.channel,
                payload=request.payload,
                priority=request.priority,
                send_at=request.send_at,
                max_retries=request.max_retries,
            )

            response = JobResponse.model_validate(job)

            if created:
                logger.info(
                    "Job scheduled: id=%s channel=%s priority=%d send_at=%s",
                    job.id, job.channel.value, job.priority, job.send_at,
                )
            else:
                logger.info(
                    "Idempotent hit: idempotency_key=%s returning existing job=%s",
                    request.idempotency_key, job.id,
                )

            return Ok((response, created))

        except Exception as e:
            logger.exception("Failed to schedule job")
            return Err(f"Failed to schedule job: {str(e)}")

    async def get_status(self, job_id: uuid.UUID) -> Result:
        job = await self._repo.get_by_id(job_id)
        if job is None:
            return Err(f"Job {job_id} not found")
        return Ok(JobStatusResponse.model_validate(job))

    async def get_metrics(self) -> MetricsResponse:
        counts = await self._repo.get_metrics()
        return MetricsResponse(**counts)
