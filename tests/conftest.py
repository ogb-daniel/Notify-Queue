

import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
import redis.asyncio as aioredis

from src.core.database import Base, get_db
from src.core.redis import get_redis
from src.main import app
from src.models import Job, JobStatus, ChannelType
from src.services.redis_lock import RedisLock


TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://notify:notify@localhost:5432/notifyqueue_test",
)

TEST_REDIS_URL = os.environ.get(
    "TEST_REDIS_URL",
    "redis://localhost:6379/1",  
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_redis():
    client = aioredis.from_url(
        TEST_REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    await client.ping()
    yield client
    await client.flushdb()  
    await client.aclose()


@pytest_asyncio.fixture
async def redis_lock(test_redis):
    return RedisLock(test_redis)


@pytest_asyncio.fixture
async def session(test_engine):
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def session_factory(test_engine):

    factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    yield factory


@pytest_asyncio.fixture
async def client(session, test_redis):
    async def _override_db():
        yield session

    def _override_redis():
        return test_redis

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_redis] = _override_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_job(session) -> Job:
    job = Job(
        idempotency_key=f"test-{uuid.uuid4().hex[:8]}",
        recipient="test@example.com",
        channel=ChannelType.EMAIL,
        payload={"subject": "Test", "body": "Hello"},
        priority=3,
        status=JobStatus.PENDING,
        send_at=datetime.now(timezone.utc),
        max_retries=5,
    )
    session.add(job)
    await session.flush()
    return job
