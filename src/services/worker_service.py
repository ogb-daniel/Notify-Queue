
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
import redis.asyncio as aioredis

from src.core.config import settings, Settings
from src.models import Job, ChannelType
from src.repositories.job_repository import JobRepository
from src.senders.base import NotificationSender
from src.senders.email_sender import EmailSender
from src.senders.sms_sender import SmsSender
from src.senders.push_sender import PushSender
from src.services.webhook_service import fire_webhook
from src.services.redis_lock import RedisLock
from src.services.redis_rate_limiter import RedisRateLimiter
from src.domain.backoff import calculate_next_retry, should_dead_letter
from src.domain.result import Ok, Err

logger = logging.getLogger(__name__)


def _build_sender_registry(
    failure_rate: float,
) -> dict[ChannelType, NotificationSender]:
    return {
        ChannelType.EMAIL: EmailSender(failure_rate=failure_rate),
        ChannelType.SMS: SmsSender(failure_rate=failure_rate),
        ChannelType.PUSH: PushSender(failure_rate=failure_rate),
    }


async def _process_single_job(
    job: Job,
    lock_token: str,
    repo: JobRepository,
    redis_lock: RedisLock,
    rate_limiter: RedisRateLimiter,
    sender: NotificationSender,
    settings: Settings,
) -> None:

    try:
        is_limited, current_count = await rate_limiter.check_rate_limit(
            job.recipient,
        )

        if is_limited:
            defer_to = await rate_limiter.next_available_slot(job.recipient)
            await repo.defer_job(job.id, defer_to)
            logger.info(
                "Job %s deferred (rate limited): recipient=%s "
                "count=%d/%d deferred_to=%s",
                job.id, job.recipient, current_count,
                settings.RATE_LIMIT_PER_RECIPIENT_PER_HOUR, defer_to,
            )
            return

        result = await sender.send(job.recipient, job.payload)

        match result:
            case Ok(receipt):
                await repo.mark_sent(job.id)
                await rate_limiter.record_send(job.recipient)
                await fire_webhook(job, event="sent")
                logger.info(
                    "Job %s sent: channel=%s recipient=%s provider_id=%s",
                    job.id, job.channel.value, job.recipient,
                    receipt.provider_message_id,
                )

            case Err(error):
                if should_dead_letter(job.attempt_count, job.max_retries):
                    await repo.move_to_dead_letter(
                        job.id,
                        reason=f"Exhausted {job.max_retries} retries",
                        last_error=error.message,
                    )
                    await fire_webhook(
                        job, event="dead_lettered", error=error.message,
                    )
                    logger.warning(
                        "Job %s dead-lettered: attempts=%d/%d error=%s",
                        job.id, job.attempt_count, job.max_retries,
                        error.message,
                    )
                else:
                    delay = calculate_next_retry(
                        attempt_count=job.attempt_count,
                        base_delay_seconds=settings.BACKOFF_BASE_SECONDS,
                        max_delay_seconds=settings.BACKOFF_MAX_SECONDS,
                    )
                    retry_at = datetime.now(timezone.utc) + delay
                    await repo.mark_failed(job.id, error.message, retry_at)
                    await fire_webhook(
                        job, event="failed", error=error.message,
                    )
                    logger.info(
                        "Job %s failed (will retry): attempt=%d/%d "
                        "retry_at=%s error=%s",
                        job.id, job.attempt_count, job.max_retries,
                        retry_at, error.message,
                    )
    finally:
        await redis_lock.release(str(job.id), lock_token)


async def run_worker(
    worker_id: str,
    session_factory: async_sessionmaker,
    redis_client: aioredis.Redis,
    shutdown_event: asyncio.Event,
) -> None:
    
    
    senders = _build_sender_registry(settings.FAILURE_RATE)
    redis_lock = RedisLock(redis_client)
    rate_limiter = RedisRateLimiter(redis_client)

    logger.info(
        "Worker %s starting (poll=%.1fs, batch=%d, redis=%s)",
        worker_id, settings.WORKER_POLL_INTERVAL_SECONDS,
        settings.WORKER_BATCH_SIZE, settings.REDIS_URL,
    )

    while not shutdown_event.is_set():
        try:
            async with session_factory() as session:
                repo = JobRepository(session, redis_lock)

                claimed_jobs = await repo.claim_next_batch(
                    worker_id=worker_id,
                    batch_size=settings.WORKER_BATCH_SIZE,
                )

                if claimed_jobs:
                    logger.info(
                        "Worker %s claimed %d jobs",
                        worker_id, len(claimed_jobs),
                    )

                    for job, lock_token in claimed_jobs:
                        sender = senders.get(job.channel)
                        if sender is None:
                            logger.error(
                                "No sender for channel %s, "
                                "dead-lettering job %s",
                                job.channel.value, job.id,
                            )
                            await repo.move_to_dead_letter(
                                job.id,
                                reason=f"Unsupported channel: "
                                       f"{job.channel.value}",
                                last_error="No sender registered",
                            )
                            await redis_lock.release(
                                str(job.id), lock_token,
                            )
                            continue

                        await _process_single_job(
                            job, lock_token, repo, redis_lock,
                            rate_limiter, sender, settings,
                        )

                    await session.commit()

            async with session_factory() as recovery_session:
                recovery_repo = JobRepository(recovery_session, redis_lock)
                recovered = await recovery_repo.recover_stale_claims()
                if recovered > 0:
                    logger.info(
                        "Worker %s recovered %d stale claims",
                        worker_id, recovered,
                    )
                await recovery_session.commit()

        except Exception as e:
            logger.exception(
                "Worker %s error in poll cycle: %s", worker_id, e,
            )

        try:
            await asyncio.wait_for(
                shutdown_event.wait(),
                timeout=settings.WORKER_POLL_INTERVAL_SECONDS,
            )
        except asyncio.TimeoutError:
            pass

    logger.info("Worker %s stopped gracefully", worker_id)
