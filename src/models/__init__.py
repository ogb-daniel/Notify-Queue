from src.core.database import Base


__all__ = ["Base"]

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)