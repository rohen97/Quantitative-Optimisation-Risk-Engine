from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from .models import DriftCheckResult


def population_stability_index(expected: np.ndarray, actual: np.ndarray, bins: int = 10, epsilon: float = 1e-8) -> float:
    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)
    expected = expected[np.isfinite(expected)]
    actual = actual[np.isfinite(actual)]
    if expected.size == 0 or actual.size == 0:
        return math.nan
    quantiles = np.linspace(0, 1, bins + 1)
    edges = np.unique(np.quantile(expected, quantiles))
    if edges.size < 3:
        edges = np.linspace(min(expected.min(), actual.min()), max(expected.max(), actual.max()), bins + 1)
    expected_counts, _ = np.histogram(expected, bins=edges)
    actual_counts, _ = np.histogram(actual, bins=edges)
    expected_pct = np.maximum(expected_counts / max(expected_counts.sum(), 1), epsilon)
    actual_pct = np.maximum(actual_counts / max(actual_counts.sum(), 1), epsilon)
    return float(np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct)))


def compare_weight_l1(current: pd.DataFrame, baseline: pd.DataFrame, ticker_column: str = "ticker", weight_column: str = "weight") -> float:
    if current.empty or baseline.empty or ticker_column not in current or ticker_column not in baseline:
        return math.nan
    current_weights = current.set_index(ticker_column).get(weight_column, pd.Series(dtype=float)).astype(float)
    baseline_weights = baseline.set_index(ticker_column).get(weight_column, pd.Series(dtype=float)).astype(float)
    aligned = pd.concat([current_weights, baseline_weights], axis=1).fillna(0.0)
    return float((aligned.iloc[:, 0] - aligned.iloc[:, 1]).abs().sum())


def run_drift_checks(repository_root: Path, production_config: dict) -> list[DriftCheckResult]:
    drift_config = production_config.get("drift", {})
    if not drift_config.get("enabled", True):
        return []
    warning = float(drift_config.get("maximum_weight_l1_change_warning", 0.20))
    critical = float(drift_config.get("maximum_weight_l1_change_critical", 0.40))
    current_path = repository_root / "reports" / "outputs" / "final_recommendations.csv"
    baseline_path = repository_root / drift_config.get("baseline_directory", "reports/outputs/production/baselines") / "final_recommendations.csv"
    if not current_path.exists() or not baseline_path.exists():
        return [
            DriftCheckResult(
                "portfolio",
                "final_recommendations",
                "weight_l1_change",
                None,
                warning,
                critical,
                "NOT_EVALUATED",
                0,
                "Current or approved baseline recommendations are missing.",
            )
        ]
    current = pd.read_csv(current_path)
    baseline = pd.read_csv(baseline_path)
    weight_column = "final_weight" if "final_weight" in current.columns else "weight"
    metric = compare_weight_l1(current, baseline, weight_column=weight_column)
    if not math.isfinite(metric):
        status = "NOT_EVALUATED"
    elif metric >= critical:
        status = "FAIL"
    elif metric >= warning:
        status = "WARNING"
    else:
        status = "PASS"
    return [
        DriftCheckResult(
            "portfolio",
            "final_recommendations",
            "weight_l1_change",
            metric if math.isfinite(metric) else None,
            warning,
            critical,
            status,
            int(max(len(current), len(baseline))),
            None,
        )
    ]
