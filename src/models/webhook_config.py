
import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    String,
    Integer,
    DateTime,
    Text,
    Enum as SAEnum,
    Index,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from src.core.database import Base
from src.models import _utcnow

class WebhookConfig(Base):
    __tablename__ = "webhook_configs"
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    events: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: ["sent", "failed", "dead_lettered"],
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
    )