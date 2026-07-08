from datetime import timedelta
import random

def calculate_next_retry(
    attempt_count: int,
    base_delay_seconds: float = 2.0,
    max_delay_seconds: float = 3600.0,
    jitter: bool = True,
) -> timedelta:
   
    delay = min(base_delay_seconds * (2 ** attempt_count), max_delay_seconds)
    if jitter:
        jitter_range = delay * 0.25
        delay = delay + random.uniform(-jitter_range, jitter_range)
        delay = max(0.0, delay)  
    return timedelta(seconds=delay)

def should_dead_letter(attempt_count: int, max_retries: int) -> bool:
    return attempt_count >= max_retries

