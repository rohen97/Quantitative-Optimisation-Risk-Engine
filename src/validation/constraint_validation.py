from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ConstraintCheckResult:
    valid: bool
    maximum_inequality_breach: float
    maximum_equality_error: float
    negative_weight_count: int
    weight_sum_error: float


def validate_weight_vector(
    weights: np.ndarray,
    inequality_matrix: np.ndarray | None = None,
    inequality_bounds: np.ndarray | None = None,
    equality_matrix: np.ndarray | None = None,
    equality_targets: np.ndarray | None = None,
    tolerance: float = 1e-6,
) -> ConstraintCheckResult:
    values = np.asarray(weights, dtype=float)
    if not np.isfinite(values).all():
        return ConstraintCheckResult(False, float("inf"), float("inf"), int((~np.isfinite(values)).sum()), float("inf"))
    negative_count = int((values < -tolerance).sum())
    weight_sum_error = float(abs(values.sum() - 1.0))
    inequality_breach = 0.0
    if inequality_matrix is not None and inequality_bounds is not None:
        inequality_breach = float(np.maximum(np.asarray(inequality_matrix) @ values - np.asarray(inequality_bounds), 0.0).max(initial=0.0))
    equality_error = 0.0
    if equality_matrix is not None and equality_targets is not None:
        equality_error = float(np.abs(np.asarray(equality_matrix) @ values - np.asarray(equality_targets)).max(initial=0.0))
    valid = negative_count == 0 and weight_sum_error <= tolerance and inequality_breach <= tolerance and equality_error <= tolerance
    return ConstraintCheckResult(valid, inequality_breach, equality_error, negative_count, weight_sum_error)


def validate_portfolio_frame(
    portfolio: pd.DataFrame,
    weight_column: str,
    maximum_single_name_weight: float,
    tolerance: float = 1e-6,
    eligibility_column: str | None = None,
) -> pd.DataFrame:
    if portfolio.empty or weight_column not in portfolio:
        return pd.DataFrame([{"check_name": "portfolio_available", "status": "FAIL", "breach_count": 1, "critical": True}])
    weights = pd.to_numeric(portfolio[weight_column], errors="coerce")
    rows = [
        {"check_name": "finite_weights", "status": "PASS" if weights.notna().all() else "FAIL", "breach_count": int(weights.isna().sum()), "critical": True},
        {"check_name": "weights_sum_to_one", "status": "PASS" if abs(weights.sum() - 1.0) <= tolerance else "FAIL", "breach_count": int(abs(weights.sum() - 1.0) > tolerance), "critical": True},
        {"check_name": "long_only", "status": "PASS" if (weights >= -tolerance).all() else "FAIL", "breach_count": int((weights < -tolerance).sum()), "critical": True},
        {"check_name": "single_name_cap", "status": "PASS" if (weights <= maximum_single_name_weight + tolerance).all() else "FAIL", "breach_count": int((weights > maximum_single_name_weight + tolerance).sum()), "critical": True},
    ]
    if eligibility_column and eligibility_column in portfolio:
        excluded = ~portfolio[eligibility_column].fillna(False).astype(bool)
        breach = excluded & (weights > tolerance)
        rows.append({"check_name": "excluded_assets_zero", "status": "PASS" if not breach.any() else "FAIL", "breach_count": int(breach.sum()), "critical": True})
    return pd.DataFrame(rows)
