from fastapi import APIRouter
from src.api.v1.jobs import router as jobs_router
from src.api.v1.metrics import router as metrics_router
from src.api.v1.webhooks import router as webhooks_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(jobs_router)
api_router.include_router(metrics_router)
api_router.include_router(webhooks_router)