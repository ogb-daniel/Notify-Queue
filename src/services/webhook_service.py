
import logging
from datetime import datetime, timezone

import httpx

from src.models import Job, JobStatus
from src.schemas import WebhookPayload
from src.core.config import get_settings

logger = logging.getLogger(__name__)


async def fire_webhook(
    job: Job,
    event: str,
    error: str | None = None,
) -> None:
    settings = get_settings()

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

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.WEBHOOK_URL,
                json=payload.model_dump(mode="json"),
                timeout=settings.WEBHOOK_TIMEOUT_SECONDS,
            )
            logger.info(
                "Webhook fired: event=%s job=%s status_code=%d",
                event, job.id, response.status_code,
            )
    except httpx.TimeoutException:
        logger.warning(
            "Webhook timeout: event=%s job=%s url=%s",
            event, job.id, settings.WEBHOOK_URL,
        )
    except Exception as e:
        logger.warning(
            "Webhook failed: event=%s job=%s error=%s",
            event, job.id, str(e),
        )
