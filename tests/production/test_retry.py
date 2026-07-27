from __future__ import annotations

from src.production.retry import RetryPolicy, retry_delay_seconds, run_with_retry


def test_retry_runs_until_success():
    calls = {"count": 0}

    def operation():
        calls["count"] += 1
        return calls["count"] >= 2

    result, attempts = run_with_retry(operation, lambda value: not value, RetryPolicy(maximum_attempts=3), sleep=lambda _: None)
    assert result is True
    assert attempts == 2


def test_retry_delay_is_capped():
    policy = RetryPolicy(initial_delay_seconds=10, maximum_delay_seconds=11, backoff_multiplier=10, jitter_seconds=0)
    assert retry_delay_seconds(policy, 3) == 11
