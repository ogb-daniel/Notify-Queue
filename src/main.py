from contextlib import asynccontextmanager
from fastapi import FastAPI
from typing import AsyncIterator
from src.core.config import settings
from src.core.database import engine, Base
from src.api.v1.api import router as api_router
import logging
import sys
from src.core.redis import init_redis, close_redis

def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting NotifyQueue API")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    init_redis()
    logger.info("Database + Redis initialized")
    yield
    await close_redis()
    logger.info("NotifyQueue API shutdown complete")



app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Distributed delayed job & notification delivery system",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.include_router(api_router)
