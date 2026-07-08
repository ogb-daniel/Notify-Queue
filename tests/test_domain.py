

from datetime import datetime, timedelta, timezone

from src.domain.backoff import calculate_next_retry, should_dead_letter
from src.domain.priority import PriorityLevel, compute_sort_key
from src.domain.result import Ok, Err


class TestCalculateNextRetry:
    def test_first_retry_is_base_delay(self):
        delay = calculate_next_retry(0, base_delay_seconds=2.0, jitter=False)
        assert delay == timedelta(seconds=2.0)

    def test_exponential_growth(self):
        delays = [
            calculate_next_retry(i, base_delay_seconds=2.0, jitter=False)
            for i in range(5)
        ]
        expected = [2.0, 4.0, 8.0, 16.0, 32.0]
        assert [d.total_seconds() for d in delays] == expected

    def test_capped_at_max(self):
        delay = calculate_next_retry(
            20, base_delay_seconds=2.0, max_delay_seconds=3600.0, jitter=False,
        )
        assert delay == timedelta(seconds=3600.0)

    def test_jitter_adds_variance(self):
        delays = {
            calculate_next_retry(3, jitter=True).total_seconds()
            for _ in range(20)
        }
        assert len(delays) > 1

    def test_never_negative(self):
        for attempt in range(10):
            delay = calculate_next_retry(attempt, jitter=True)
            assert delay.total_seconds() >= 0


class TestShouldDeadLetter:
    def test_under_limit(self):
        assert should_dead_letter(3, 5) is False

    def test_at_limit(self):
        assert should_dead_letter(5, 5) is True

    def test_over_limit(self):
        assert should_dead_letter(7, 5) is True

    def test_zero_retries(self):
        assert should_dead_letter(0, 0) is True

    def test_first_attempt_with_retries(self):
        assert should_dead_letter(1, 5) is False


class TestPriority:
    def test_critical_before_low(self):
        critical = compute_sort_key(1, datetime(2024, 1, 1, 12, 0))
        low = compute_sort_key(4, datetime(2024, 1, 1, 10, 0))
        assert critical < low

    def test_same_priority_fifo(self):
        first = compute_sort_key(3, datetime(2024, 1, 1, 10, 0))
        second = compute_sort_key(3, datetime(2024, 1, 1, 12, 0))
        assert first < second

    def test_priority_enum_values(self):
        assert PriorityLevel.CRITICAL < PriorityLevel.BULK
        assert int(PriorityLevel.CRITICAL) == 1
        assert int(PriorityLevel.BULK) == 5


class TestResult:
    def test_ok_is_ok(self):
        r = Ok(42)
        assert r.is_ok() is True
        assert r.is_err() is False
        assert r.value == 42

    def test_err_is_err(self):
        r = Err("something broke")
        assert r.is_err() is True
        assert r.is_ok() is False
        assert r.error == "something broke"
