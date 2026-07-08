
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from src.domain.result import Result


@dataclass(frozen=True)
class SentReceipt:
    delivered_at: datetime
    provider_message_id: str = ""


@dataclass(frozen=True)
class SendError:
    message: str
    is_retryable: bool = True


class NotificationSender(Protocol):


    async def send(
        self,
        job_id: str,
        recipient: str,
        payload: dict,
    ) -> Result:
    
        ...
