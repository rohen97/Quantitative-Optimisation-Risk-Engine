from __future__ import annotations

import numpy as np


def benjamini_hochberg(p_values: list[float]) -> list[float]:
    values = np.asarray(p_values, dtype=float)
    if values.size == 0:
        return []
    order = np.argsort(values)
    adjusted = np.empty_like(values)
    running = 1.0
    for rank_index in range(values.size - 1, -1, -1):
        original_index = order[rank_index]
        rank = rank_index + 1
        running = min(running, float(values[original_index]) * values.size / rank)
        adjusted[original_index] = min(running, 1.0)
    return adjusted.tolist()
