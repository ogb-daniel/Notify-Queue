
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from src.models import ChannelType, JobStatus
from src.domain.priority import PriorityLevel

class CreateJobRequest(BaseModel):
    recipient: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Recipient identifier (email, phone, device token)",
        examples=["user@example.com"],
    )
    channel: ChannelType = Field(
        ...,
        description="Delivery channel",
        examples=["email"],
    )
    payload: dict = Field(
        default_factory=dict,
        description="Notification content (channel-specific)",
        examples=[{"subject": "Hello", "body": "World"}],
    )
    priority: int = Field(
        default=PriorityLevel.MEDIUM,
        ge=PriorityLevel.CRITICAL,
        le=PriorityLevel.BULK,
        description="Priority level (1=critical, 5=bulk)",
    )
    send_at: Optional[datetime] = Field(
        default=None,
        description="Absolute UTC time to send. Mutually exclusive with delay_seconds.",
    )
    delay_seconds: Optional[int] = Field(
        default=None,
        ge=0,
        description="Delay in seconds from now. Mutually exclusive with send_at.",
    )
    idempotency_key: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique key to prevent duplicate submissions",
        examples=["order-123-confirmation"],
    )
    max_retries: int = Field(
        default=5,
        ge=0,
        le=20,
        description="Maximum retry attempts before dead-lettering",
    )
    @model_validator(mode="after")
    def validate_scheduling(self) -> "CreateJobRequest":
        if self.send_at is None and self.delay_seconds is None:
            self.send_at = datetime.now(timezone.utc)
        elif self.send_at is not None and self.delay_seconds is not None:
            raise ValueError(
                "Provide either 'send_at' or 'delay_seconds', not both"
            )
        elif self.delay_seconds is not None:
            self.send_at = datetime.now(timezone.utc) + timedelta(
                seconds=self.delay_seconds
            )
        return self
    @field_validator("recipient")
    @classmethod
    def validate_recipient_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Recipient must not be empty or whitespace")
        return v


class JobResponse(BaseModel):
    id: uuid.UUID
    idempotency_key: str
    recipient: str
    channel: ChannelType
    payload: dict
    priority: int
    status: JobStatus
    send_at: datetime
    attempt_count: int
    max_retries: int
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class JobStatusResponse(BaseModel):
    id: uuid.UUID
    status: JobStatus
    attempt_count: int
    max_retries: int
    last_error: Optional[str] = None
    send_at: datetime
    created_at: datetime
    model_config = {"from_attributes": True}

class MetricsResponse(BaseModel):
    pending: int = 0
    claimed: int = 0
    sent: int = 0
    failed: int = 0
    dead_lettered: int = 0
    total: int = 0

class RegisterWebhookRequest(BaseModel):
    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="URL to POST status change callbacks to",
        examples=["https://myapp.com/webhook"],
    )
    events: list[str] = Field(
        default=["sent", "failed", "dead_lettered"],
        description="Which status changes to notify about",
    )

class WebhookPayload(BaseModel):
    event: str
    job_id: uuid.UUID
    status: JobStatus
    recipient: str
    channel: ChannelType
    attempt_count: int
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))