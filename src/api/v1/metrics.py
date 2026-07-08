
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.redis import get_redis
from src.schemas import MetricsResponse
from src.services.job_service import JobService
from src.services.redis_lock import RedisLock

router = APIRouter(tags=["metrics"])


def _get_job_service(
    session: AsyncSession = Depends(get_db),
    redis_client=Depends(get_redis),
) -> JobService:
    redis_lock = RedisLock(redis_client)
    return JobService(session, redis_lock)


@router.get(
    "/metrics",
    response_model=MetricsResponse,
)
async def get_metrics(
    service: JobService = Depends(_get_job_service),
) -> MetricsResponse:
    return await service.get_metrics()
