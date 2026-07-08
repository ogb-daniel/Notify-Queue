from src.core.database import Base
from src.models.job import Job
from src.models.dead_letter_job import DeadLetterJob
from src.models.webhook_config import WebhookConfig

__all__ = ["Base", "Job", "DeadLetterJob","WebhookConfig"]

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)