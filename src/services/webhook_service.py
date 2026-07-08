
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Job, WebhookConfig
from src.schemas import WebhookPayload
from src.core.config import settings
from src.repositories.job_repository import JobRepository
from src.services.redis_lock import RedisLock

logger = logging.getLogger(__name__)


async def fire_webhooks(
    job: Job,
    event: str,
    session: AsyncSession,
    redis_lock: RedisLock,
    error: str | None = None,
) -> None:
    
    repo = JobRepository(session, redis_lock)
    active_webhooks = await repo.get_active_webhooks()

    matching_webhooks = [
        wh for wh in active_webhooks
        if event in wh.events
    ]

    if not matching_webhooks:
        return

    payload = WebhookPayload(
        event=event,
        job_id=job.id,
        status=job.status,
        recipient=job.recipient,
        channel=job.channel,
        attempt_count=job.attempt_count,
        error=error,
        timestamp=datetime.now(timezone.utc),
    )

    payload_json = payload.model_dump(mode="json")

    async with httpx.AsyncClient(timeout=settings.WEBHOOK_TIMEOUT_SECONDS) as client:
        for webhook in matching_webhooks:
            try:
                response = await client.post(
                    webhook.url,
                    json=payload_json,
                )
                logger.info(
                    "Webhook fired: event=%s job=%s url=%s status_code=%d",
                    event, job.id, webhook.url, response.status_code,
                )
            except httpx.TimeoutException:
                logger.warning(
                    "Webhook timeout: event=%s job=%s url=%s",
                    event, job.id, webhook.url,
                )
            except Exception as e:
                logger.warning(
                    "Webhook failed: event=%s job=%s url=%s error=%s",
                    event, job.id, webhook.url, str(e),
                )
