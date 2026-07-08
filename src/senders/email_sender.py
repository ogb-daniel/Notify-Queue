
import asyncio
import random
import uuid
from datetime import datetime, timezone

from src.domain.result import Ok, Err, Result
from src.senders.base import SentReceipt, SendError


class EmailSender:
   
    def __init__(self, failure_rate: float = 0.2):
        
        self.failure_rate = max(0.0, min(1.0, failure_rate))

    async def send(
        self,
        recipient: str,
        payload: dict,
    ) -> Result:

        # Simulate network latency (100–500ms)
        await asyncio.sleep(random.uniform(0.1, 0.5))

        if random.random() < self.failure_rate:
            return Err(SendError(
                message=f"Simulated SMTP failure for {recipient}",
                is_retryable=True,
            ))

        return Ok(SentReceipt(
            delivered_at=datetime.now(timezone.utc),
            provider_message_id=f"email-{uuid.uuid4().hex[:8]}",
        ))
