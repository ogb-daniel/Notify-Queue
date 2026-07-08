

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.redis import get_redis
from src.schemas import CreateJobRequest, JobResponse, JobStatusResponse
from src.services.job_service import JobService
from src.services.redis_lock import RedisLock
from src.domain.result import Ok, Err

logger = logging.getLogger(__name__)

router = APIRouter(tags=["jobs"])


def _get_job_service(
    session: AsyncSession = Depends(get_db),
) -> JobService:
    redis_lock = RedisLock(get_redis())
    return JobService(session, redis_lock)


@router.post(
    "/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "Job with this idempotency key already exists"},
    },
)
async def schedule_job(
    request: CreateJobRequest,
    service: JobService = Depends(_get_job_service),
) -> JobResponse:

    result = await service.schedule_job(request)

    match result:
        case Ok((response, created)):
            if not created:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "message": "Job with this idempotency key already exists",
                        "existing_job": response.model_dump(mode="json"),
                    },
                )
            return response

        case Err(error):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(error),
            )


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
)
async def get_job_status(
    job_id: uuid.UUID,
    service: JobService = Depends(_get_job_service),
) -> JobStatusResponse:
    result = await service.get_status(job_id)

    match result:
        case Ok(response):
            return response
        case Err(error):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error),
            )
