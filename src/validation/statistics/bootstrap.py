from __future__ import annotations

import numpy as np


def block_bootstrap_interval(
    values: np.ndarray,
    statistic=np.mean,
    samples: int = 1000,
    confidence_level: float = 0.95,
    block_size: int = 20,
    seed: int = 42,
) -> tuple[float, float]:
    data = np.asarray(values, dtype=float)
    data = data[np.isfinite(data)]
    if data.size == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    block = max(1, min(int(block_size), data.size))
    starts = np.arange(max(data.size - block + 1, 1))
    estimates = np.empty(samples, dtype=float)
    for index in range(samples):
        chunks: list[np.ndarray] = []
        while sum(len(chunk) for chunk in chunks) < data.size:
            start = int(rng.choice(starts))
            chunks.append(data[start : start + block])
        sample = np.concatenate(chunks)[: data.size]
        estimates[index] = float(statistic(sample))
    tail = (1.0 - confidence_level) / 2.0
    return float(np.quantile(estimates, tail)), float(np.quantile(estimates, 1.0 - tail))
