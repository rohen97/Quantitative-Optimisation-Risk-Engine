from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class VaRBacktestResult:
    observations: int
    breaches: int
    expected_breaches: float
    breach_rate: float
    expected_breach_rate: float
    kupiec_statistic: float
    kupiec_pvalue: float
    passed: bool


def _chi_square_one_df_survival(statistic: float) -> float:
    return math.erfc(math.sqrt(max(statistic, 0.0) / 2.0))


def _kupiec_from_violations(violations: pd.Series | np.ndarray, expected_rate: float) -> dict[str, float | int]:
    values = np.asarray(violations, dtype=bool)
    count = values.size
    breaches = int(values.sum())
    if count == 0:
        return {"observations": 0, "violations": 0, "violation_rate": float("nan"), "lr_statistic": float("nan"), "p_value": float("nan")}
    observed = min(max(breaches / count, 1e-12), 1.0 - 1e-12)
    expected = min(max(expected_rate, 1e-12), 1.0 - 1e-12)
    null_log_likelihood = (count - breaches) * math.log(1.0 - expected) + breaches * math.log(expected)
    alternative_log_likelihood = (count - breaches) * math.log(1.0 - observed) + breaches * math.log(observed)
    statistic = -2.0 * (null_log_likelihood - alternative_log_likelihood)
    return {"observations": count, "violations": breaches, "violation_rate": breaches / count, "lr_statistic": statistic, "p_value": _chi_square_one_df_survival(statistic)}


def kupiec_test(
    losses: np.ndarray,
    var_forecasts: np.ndarray,
    confidence_level: float,
    pvalue_threshold: float = 0.05,
) -> VaRBacktestResult:
    loss_array = np.asarray(losses, dtype=float)
    var_array = np.asarray(var_forecasts, dtype=float)
    valid = np.isfinite(loss_array) & np.isfinite(var_array)
    loss_array, var_array = loss_array[valid], var_array[valid]
    if loss_array.size == 0:
        raise ValueError("No valid VaR observations.")
    result = _kupiec_from_violations(loss_array > var_array, 1.0 - confidence_level)
    return VaRBacktestResult(
        observations=int(result["observations"]),
        breaches=int(result["violations"]),
        expected_breaches=float(result["observations"]) * (1.0 - confidence_level),
        breach_rate=float(result["violation_rate"]),
        expected_breach_rate=1.0 - confidence_level,
        kupiec_statistic=float(result["lr_statistic"]),
        kupiec_pvalue=float(result["p_value"]),
        passed=float(result["p_value"]) >= pvalue_threshold,
    )


def christoffersen_independence_test(violations: pd.Series | np.ndarray) -> dict[str, float]:
    values = np.asarray(violations, dtype=int)
    if values.size < 2:
        return {"lr_statistic": float("nan"), "p_value": float("nan")}
    previous, current = values[:-1], values[1:]
    n00 = int(((previous == 0) & (current == 0)).sum())
    n01 = int(((previous == 0) & (current == 1)).sum())
    n10 = int(((previous == 1) & (current == 0)).sum())
    n11 = int(((previous == 1) & (current == 1)).sum())
    pi = (n01 + n11) / max(n00 + n01 + n10 + n11, 1)
    pi0 = n01 / max(n00 + n01, 1)
    pi1 = n11 / max(n10 + n11, 1)
    def term(count: int, probability: float) -> float:
        return count * math.log(min(max(probability, 1e-12), 1.0 - 1e-12))
    null_ll = term(n00 + n10, 1.0 - pi) + term(n01 + n11, pi)
    alt_ll = term(n00, 1.0 - pi0) + term(n01, pi0) + term(n10, 1.0 - pi1) + term(n11, pi1)
    statistic = max(-2.0 * (null_ll - alt_ll), 0.0)
    return {"lr_statistic": statistic, "p_value": _chi_square_one_df_survival(statistic)}


def backtest_var(realised_returns: pd.Series, forecast_var: pd.Series, confidence_level: float) -> dict[str, float | int]:
    frame = pd.DataFrame({"return": realised_returns, "var": forecast_var}).apply(pd.to_numeric, errors="coerce").dropna()
    losses = -frame["return"].to_numpy(dtype=float)
    var_losses = -frame["var"].to_numpy(dtype=float)
    kupiec_result = kupiec_test(losses, var_losses, confidence_level)
    violations = losses > var_losses
    kupiec = {
        "observations": kupiec_result.observations,
        "violations": kupiec_result.breaches,
        "violation_rate": kupiec_result.breach_rate,
        "lr_statistic": kupiec_result.kupiec_statistic,
        "p_value": kupiec_result.kupiec_pvalue,
    }
    independence = christoffersen_independence_test(violations)
    return {**kupiec, "confidence_level": confidence_level, "christoffersen_lr": independence["lr_statistic"], "christoffersen_p_value": independence["p_value"]}
