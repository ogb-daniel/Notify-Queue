from contextlib import asynccontextmanager
from fastapi import FastAPI
from typing import AsyncIterator
from src.core.config import settings
from src.core.database import engine, Base
from src.api.v1.api import router as api_router

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    print("Startup")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    print("Shutdown")

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan, docs_url='/api/docs', openapi_url='/api/openapi.json')

app.include_router(api_router)
