
import argparse
import asyncio
import random
import uuid
import logging
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.config import settings
from src.core.database import engine, Base
from src.core.redis import init_redis, close_redis
from src.models import Job, ChannelType, JobStatus

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


def generate_jobs(count: int) -> list[Job]:
    now = datetime.now(timezone.utc)
    jobs = []
    
    channels = list(ChannelType)
    
    for i in range(count):
        if random.random() < 0.8:
            send_at = now
        else:
            send_at = now + timedelta(seconds=random.randint(10, 600))
            
        p_rand = random.random()
        if p_rand < 0.1:
            priority = 1
        elif p_rand < 0.3:
            priority = 2
        elif p_rand < 0.7:
            priority = 3
        elif p_rand < 0.9:
            priority = 4
        else:
            priority = 5

        channel = random.choice(channels)
        
        recipient = f"user_{random.randint(1, 100)}@example.com"
        
        job = Job(
            idempotency_key=f"seed-{uuid.uuid4().hex}",
            recipient=recipient,
            channel=channel,
            payload={"message": f"Hello {i}", "data": uuid.uuid4().hex},
            priority=priority,
            status=JobStatus.PENDING,
            send_at=send_at,
            max_retries=5,
        )
        jobs.append(job)
        
    return jobs


async def seed_data(count: int, batch_size: int):
    logger.info("Initializing database and Redis...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    await init_redis()
    
    SessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    logger.info("Generating %d jobs...", count)
    all_jobs = generate_jobs(count)
    
    logger.info("Inserting jobs in batches of %d...", batch_size)
    inserted = 0
    
    async with SessionLocal() as session:
        for i in range(0, len(all_jobs), batch_size):
            batch = all_jobs[i : i + batch_size]
            session.add_all(batch)
            await session.commit()
            inserted += len(batch)
            logger.info("Inserted %d/%d jobs", inserted, count)
            
    logger.info("Successfully seeded %d jobs", inserted)
    
    await close_redis()
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Seed the NotifyQueue database.")
    parser.add_argument("--count", type=int, default=1000, help="Number of jobs to insert")
    parser.add_argument("--batch-size", type=int, default=100, help="Insert batch size")
    args = parser.parse_args()
    
    asyncio.run(seed_data(args.count, args.batch_size))


if __name__ == "__main__":
    main()
