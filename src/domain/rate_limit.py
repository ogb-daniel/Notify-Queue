def is_rate_limited(
    recent_send_count: int,
    max_per_hour: int,
) -> bool:
    return recent_send_count >= max_per_hour


def next_available_slot(
    oldest_send_in_window: datetime,
    window_size: timedelta = timedelta(hours=1),
) -> datetime:
    return oldest_send_in_window + window_size