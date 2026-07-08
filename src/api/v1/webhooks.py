
import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.redis import get_redis
from src.schemas import RegisterWebhookRequest, WebhookPayload
from src.repositories.job_repository import JobRepository
from src.services.redis_lock import RedisLock

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
async def register_webhook(
    request: RegisterWebhookRequest,
    session: AsyncSession = Depends(get_db),
) -> dict:
    redis_lock = RedisLock(get_redis())
    repo = JobRepository(session, redis_lock)
    config = await repo.create_webhook_config(
        url=request.url,
        events=request.events,
    )
    await session.commit()
    return {
        "id": str(config.id),
        "url": config.url,
        "events": config.events,
        "message": "Webhook registered successfully",
    }


@router.post(
    "/receive",
    status_code=status.HTTP_200_OK,
)
async def receive_webhook(payload: WebhookPayload) -> dict:
    logger.info(
        "Webhook received: event=%s job_id=%s status=%s recipient=%s",
        payload.event,
        payload.job_id,
        payload.status.value,
        payload.recipient,
    )
    return {
        "received": True,
        "event": payload.event,
        "job_id": str(payload.job_id),
    }
