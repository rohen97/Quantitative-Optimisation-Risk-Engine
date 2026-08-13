from __future__ import annotations

import numpy as np
from scipy.stats import t


def paired_mean_test(left: np.ndarray, right: np.ndarray) -> dict[str, float]:
    a = np.asarray(left, dtype=float)
    b = np.asarray(right, dtype=float)
    valid = np.isfinite(a) & np.isfinite(b)
    differences = a[valid] - b[valid]
    if differences.size < 2:
        return {"mean_difference": float("nan"), "t_statistic": float("nan"), "p_value": float("nan")}
    standard_error = differences.std(ddof=1) / np.sqrt(differences.size)
    statistic = differences.mean() / standard_error if standard_error > 0 else 0.0
    p_value = 2.0 * t.sf(abs(float(statistic)), differences.size - 1)
    return {"mean_difference": float(differences.mean()), "t_statistic": float(statistic), "p_value": float(p_value)}
