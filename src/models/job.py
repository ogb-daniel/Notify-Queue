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

class ChannelType(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"

class JobStatus(str, enum.Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    SENT = "sent"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[ChannelType] = mapped_column(
        SAEnum(ChannelType, name="channel_type"),
        nullable=False,
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3, 
    )
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, name="job_status"),
        nullable=False,
        default=JobStatus.PENDING,
    )
    send_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    claimed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=5)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
    )
    dead_letter: Mapped["DeadLetterJob | None"] = relationship(
        back_populates="original_job",
        uselist=False,
    )
    __table_args__ = (
        Index(
            "ix_jobs_polling",
            "status", "priority", "send_at",
        ),
        Index(
            "ix_jobs_recipient_rate_limit",
            "recipient", "status", "created_at",
        ),
    )
    def __repr__(self) -> str:
        return (
            f"<Job id={self.id} channel={self.channel.value} "
            f"status={self.status.value} priority={self.priority}>"
        )
