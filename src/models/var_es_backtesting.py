from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats


def calculate_var(returns, level: float = 0.05) -> float:
    return float(np.nanquantile(pd.Series(returns).dropna(), level))


def calculate_cvar(returns, level: float = 0.05) -> float:
    data = pd.Series(returns).dropna()
    if data.empty:
        return 0.0
    var = calculate_var(data, level)
    return float(data[data <= var].mean())


def calculate_expected_shortfall(returns, level: float = 0.05) -> float:
    return calculate_cvar(returns, level)


def var_exceedance_rate(realized_returns, var_forecast) -> float:
    realized = pd.Series(realized_returns).reset_index(drop=True)
    var = pd.Series(var_forecast).reset_index(drop=True)
    return float((realized < var).mean())


def kupiec_test(realized_returns, var_forecast, alpha: float = 0.05) -> dict[str, float]:
    realized = pd.Series(realized_returns).reset_index(drop=True)
    var = pd.Series(var_forecast).reset_index(drop=True)
    hits = int((realized < var).sum())
    n_obs = int(len(realized))
    if n_obs == 0:
        return {"kupiec_statistic": 0.0, "kupiec_p_value": 1.0, "exceedance_rate": 0.0}
    phat = np.clip(hits / n_obs, 1e-8, 1 - 1e-8)
    alpha = np.clip(alpha, 1e-8, 1 - 1e-8)
    likelihood_null = (1 - alpha) ** (n_obs - hits) * alpha**hits
    likelihood_alt = (1 - phat) ** (n_obs - hits) * phat**hits
    statistic = -2 * math.log(max(likelihood_null, 1e-300) / max(likelihood_alt, 1e-300))
    return {
        "kupiec_statistic": float(statistic),
        "kupiec_p_value": float(1 - stats.chi2.cdf(statistic, df=1)),
        "exceedance_rate": float(hits / n_obs),
    }


def christoffersen_independence_test_placeholder(realized_returns, var_forecast) -> dict[str, float]:
    """Placeholder for future clustered-exceedance testing."""
    return {"christoffersen_statistic": 0.0, "christoffersen_p_value": 1.0}


def expected_shortfall_backtest_placeholder(realized_returns, es_forecast) -> dict[str, float]:
    """Placeholder for future ES backtests; reports realized tail mean gap."""
    realized = pd.Series(realized_returns).dropna()
    es = pd.Series(es_forecast).dropna()
    if realized.empty or es.empty:
        return {"expected_shortfall_gap": 0.0}
    tail = realized[realized <= realized.quantile(0.05)]
    return {"expected_shortfall_gap": float(tail.mean() - es.mean())}


def build_var_es_backtest_report(realized_returns, forecasts: pd.DataFrame, horizon: int = 12) -> pd.DataFrame:
    """Create VaR/ES backtesting report for available mock realized returns."""
    realized = pd.Series(realized_returns).fillna(0).reset_index(drop=True)
    rows = []
    for alpha, suffix in [(0.05, "5"), (0.01, "1")]:
        var_col = f"var_{suffix}_{horizon}m"
        es_col = f"expected_shortfall_{suffix}_{horizon}m"
        if var_col not in forecasts:
            continue
        kupiec = kupiec_test(realized, forecasts[var_col].reset_index(drop=True), alpha)
        es = expected_shortfall_backtest_placeholder(realized, forecasts.get(es_col, forecasts[var_col]).reset_index(drop=True))
        rows.append({"horizon": horizon, "alpha": alpha, **kupiec, **christoffersen_independence_test_placeholder(realized, forecasts[var_col]), **es})
    return pd.DataFrame(rows)
