
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

class DeadLetterJob(Base):
    __tablename__ = "dead_letter_jobs"
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    original_job_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("jobs.id"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    moved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
    )
    
    original_job: Mapped["Job"] = relationship(back_populates="dead_letter")
    def __repr__(self) -> str:
        return f"<DeadLetterJob id={self.id} job_id={self.original_job_id}>"