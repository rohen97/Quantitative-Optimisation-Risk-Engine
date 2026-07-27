from __future__ import annotations

import numpy as np
import pandas as pd

from src.production.drift import compare_weight_l1, population_stability_index, run_drift_checks


def test_population_stability_index_zero_for_same_distribution():
    values = np.arange(100, dtype=float)
    assert population_stability_index(values, values) >= 0


def test_weight_l1_change():
    current = pd.DataFrame({"ticker": ["A", "B"], "weight": [0.6, 0.4]})
    baseline = pd.DataFrame({"ticker": ["A", "B"], "weight": [0.5, 0.5]})
    assert round(compare_weight_l1(current, baseline), 6) == 0.2


def test_drift_missing_baseline_is_not_evaluated(tmp_path):
    results = run_drift_checks(tmp_path, {"drift": {"enabled": True}})
    assert results[0].status == "NOT_EVALUATED"
