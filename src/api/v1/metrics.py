
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.schemas import MetricsResponse
from src.services.job_service import JobService

router = APIRouter(tags=["metrics"])


def _get_job_service(
    session: AsyncSession = Depends(get_db),
) -> JobService:
    return JobService(session)


@router.get(
    "/metrics",
    response_model=MetricsResponse,
)
async def get_metrics(
    service: JobService = Depends(_get_job_service),
) -> MetricsResponse:
    return await service.get_metrics()
