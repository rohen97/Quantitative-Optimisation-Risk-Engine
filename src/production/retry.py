from __future__ import annotations

from dataclasses import dataclass
import random
import time
from typing import Callable, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    enabled: bool = True
    maximum_attempts: int = 3
    initial_delay_seconds: float = 10.0
    maximum_delay_seconds: float = 120.0
    backoff_multiplier: float = 2.0
    jitter_seconds: float = 3.0
    retryable_exit_codes: tuple[int, ...] = (75, 111)

    @classmethod
    def from_config(cls, config: dict) -> "RetryPolicy":
        return cls(
            enabled=bool(config.get("enabled", True)),
            maximum_attempts=int(config.get("maximum_attempts", 3)),
            initial_delay_seconds=float(config.get("initial_delay_seconds", 10)),
            maximum_delay_seconds=float(config.get("maximum_delay_seconds", 120)),
            backoff_multiplier=float(config.get("backoff_multiplier", 2.0)),
            jitter_seconds=float(config.get("jitter_seconds", 3)),
            retryable_exit_codes=tuple(int(code) for code in config.get("retryable_exit_codes", [75, 111])),
        )


def retry_delay_seconds(policy: RetryPolicy, attempt_index: int, seed: int = 0) -> float:
    base = policy.initial_delay_seconds * (policy.backoff_multiplier ** max(attempt_index - 1, 0))
    rng = random.Random(seed + attempt_index)
    jitter = rng.uniform(0.0, max(policy.jitter_seconds, 0.0))
    return min(policy.maximum_delay_seconds, base + jitter)


def run_with_retry(
    operation: Callable[[], T],
    is_retryable_result: Callable[[T], bool],
    policy: RetryPolicy,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[T, int]:
    attempts = 0
    while True:
        attempts += 1
        result = operation()
        if not policy.enabled or not is_retryable_result(result) or attempts >= policy.maximum_attempts:
            return result, attempts
        sleep(retry_delay_seconds(policy, attempts))
