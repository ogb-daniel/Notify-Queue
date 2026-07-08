

import argparse
import asyncio
import logging
import signal
import uuid
import sys

from src.core.config import settings
from src.core.redis import init_redis, close_redis, get_redis
from src.services.worker_service import run_worker


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="NotifyQueue Worker",
    )
    parser.add_argument(
        "--worker-id",
        type=str,
        default=None,
        help="Unique worker identifier (auto-generated if not provided)",
    )
    return parser.parse_args()


async def main() -> None:
    setup_logging()
    args = parse_args()
    logger = logging.getLogger(__name__)

    worker_id = args.worker_id or f"worker-{uuid.uuid4().hex[:8]}"

    redis_client = init_redis()

    await redis_client.ping()
    logger.info("Redis connected: %s", f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0")

    shutdown_event = asyncio.Event()

    def _signal_handler(sig: signal.Signals) -> None:
        logger.info("Received %s - shutting down worker %s", sig.name, worker_id)
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler, sig)

    try:
        logger.info("Starting worker: %s", worker_id)
        await run_worker(
            worker_id=worker_id,
            session_factory=_session_factory,
            redis_client=redis_client,
            shutdown_event=shutdown_event,
        )
    finally:
        await close_redis()
        logger.info("Worker %s shutdown complete", worker_id)


if __name__ == "__main__":
    asyncio.run(main())
