from contextlib import asynccontextmanager
from fastapi import FastAPI
from typing import AsyncIterator

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    print("Startup")
    yield
    print("Shutdown")

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan, docs_url='/api/docs', openapi_url='/api/openapi.json')