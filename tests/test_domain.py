

from datetime import datetime, timedelta, timezone

from src.domain.backoff import calculate_next_retry, should_dead_letter
from src.domain.rate_limit import is_rate_limited, next_available_slot
from src.domain.priority import PriorityLevel, compute_sort_key
from src.domain.result import Ok, Err, map_result, bind_result



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



class TestIsRateLimited:
    def test_under_limit(self):
        assert is_rate_limited(5, 10) is False

    def test_at_limit(self):
        assert is_rate_limited(10, 10) is True

    def test_over_limit(self):
        assert is_rate_limited(15, 10) is True

    def test_zero_sends(self):
        assert is_rate_limited(0, 10) is False


class TestNextAvailableSlot:
    def test_one_hour_window(self):
        oldest = datetime(2024, 1, 1, 10, 5, tzinfo=timezone.utc)
        expected = datetime(2024, 1, 1, 11, 5, tzinfo=timezone.utc)
        assert next_available_slot(oldest) == expected

    def test_custom_window(self):
        oldest = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        result = next_available_slot(oldest, timedelta(minutes=30))
        expected = datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc)
        assert result == expected



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

    def test_map_ok(self):
        r = map_result(Ok(5), lambda x: x * 2)
        assert r == Ok(10)

    def test_map_err_passes_through(self):
        r = map_result(Err("fail"), lambda x: x * 2)
        assert r == Err("fail")

    def test_bind_ok(self):
        r = bind_result(Ok(5), lambda x: Ok(x * 2))
        assert r == Ok(10)

    def test_bind_err_passes_through(self):
        r = bind_result(Err("fail"), lambda x: Ok(x * 2))
        assert r == Err("fail")

    def test_bind_chain_stops_on_first_err(self):
        r = bind_result(
            Ok(5),
            lambda x: Err("broke") if x > 3 else Ok(x),
        )
        assert r == Err("broke")
