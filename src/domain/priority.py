from datetime import datetime
from enum import IntEnum
class PriorityLevel(IntEnum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    BULK = 5

def compute_sort_key(priority: int, send_at: datetime) -> tuple[int, float]:
    return (priority, send_at.timestamp())