from __future__ import annotations

import pandas as pd

from src.validation.portfolio_backtesting import calculate_portfolio_performance


def validate_regime_probabilities(data: pd.DataFrame, probability_columns: list[str], tolerance: float = 0.001) -> pd.DataFrame:
    if data.empty or not set(probability_columns).issubset(data):
        return pd.DataFrame([{"check_name": "regime_probabilities_available", "status": "NOT_EVALUATED", "maximum_sum_error": float("nan")}])
    probabilities = data[probability_columns].apply(pd.to_numeric, errors="coerce")
    invalid = (~probabilities.apply(lambda column: column.between(0.0, 1.0))).any(axis=1)
    sum_error = (probabilities.sum(axis=1) - 1.0).abs()
    passed = not invalid.any() and bool((sum_error <= tolerance).all())
    return pd.DataFrame([{"check_name": "regime_probabilities_normalised", "status": "PASS" if passed else "FAIL", "maximum_sum_error": float(sum_error.max()), "invalid_rows": int(invalid.sum())}])


def performance_by_regime(data: pd.DataFrame, return_column: str, regime_column: str, minimum_observations: int = 20) -> pd.DataFrame:
    if data.empty or return_column not in data or regime_column not in data:
        return pd.DataFrame()
    rows = []
    for regime, group in data.groupby(regime_column, dropna=False):
        if len(group) < minimum_observations:
            rows.append({"regime": regime, "observations": len(group), "status": "INSUFFICIENT_DATA"})
            continue
        rows.append({"regime": regime, "status": "EVALUATED", **calculate_portfolio_performance(group[return_column]).__dict__})
    return pd.DataFrame(rows)
