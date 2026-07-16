from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from src.models.distributions import distribution_cdf
from src.models.nll_losses import normal_nll, skewed_student_t_nll_placeholder, student_t_nll


def log_predictive_score(realized_returns, distribution_name: str, mu, sigma, nu=None, xi=None) -> float:
    """Return mean log predictive score, where higher is better."""
    if distribution_name == "normal":
        nll = normal_nll(realized_returns, mu, sigma)["mean_nll"]
    elif distribution_name == "student_t":
        nll = student_t_nll(realized_returns, mu, sigma, 8 if nu is None else nu)["mean_nll"]
    else:
        nll = skewed_student_t_nll_placeholder(realized_returns, mu, sigma, 8 if nu is None else nu, 1 if xi is None else xi)["mean_nll"]
    return float(-nll)


def continuous_ranked_probability_score(realized_returns, mu, sigma) -> float:
    """Documented empirical CRPS approximation based on absolute standardized forecast error."""
    realized = np.asarray(realized_returns, dtype=float)
    score = np.abs(realized - np.asarray(mu, dtype=float)) / np.maximum(np.asarray(sigma, dtype=float), 1e-8)
    return float(np.mean(score))


def pit_values(realized_returns, distribution_name: str, mu, sigma, nu=None, xi=None) -> pd.Series:
    """Probability integral transform values: forecast CDF evaluated at realized returns."""
    values = distribution_cdf(distribution_name, realized_returns, mu, sigma, nu, xi)
    return pd.Series(np.clip(values, 0, 1))


def pit_uniformity_diagnostic(pit: pd.Series) -> dict[str, float]:
    pit = pd.Series(pit).dropna().clip(0, 1)
    if pit.empty:
        return {"pit_mean": 0.5, "pit_std": 0.0, "pit_ks_statistic": 0.0, "pit_ks_p_value": 1.0}
    ks = stats.kstest(pit, "uniform")
    return {
        "pit_mean": float(pit.mean()),
        "pit_std": float(pit.std(ddof=0)),
        "pit_ks_statistic": float(ks.statistic),
        "pit_ks_p_value": float(ks.pvalue),
    }


def quantile_coverage(realized_returns, lower_quantile, upper_quantile) -> float:
    realized = pd.Series(realized_returns)
    return float(((realized >= lower_quantile) & (realized <= upper_quantile)).mean())


def calibration_error(realized_returns, predicted_returns) -> float:
    return float(abs(pd.Series(realized_returns).mean() - pd.Series(predicted_returns).mean()))


def build_probabilistic_validation(realized_returns, forecasts: pd.DataFrame, horizon: int = 12) -> pd.DataFrame:
    """Build a compact probabilistic validation table for model outputs."""
    if forecasts.empty:
        return pd.DataFrame()
    realized = pd.Series(realized_returns).fillna(0).reset_index(drop=True)
    mu = forecasts[f"distribution_mu_{horizon}m"].reset_index(drop=True)
    sigma = forecasts[f"distribution_sigma_{horizon}m"].reset_index(drop=True)
    nu = forecasts[f"distribution_nu_{horizon}m"].reset_index(drop=True)
    xi = forecasts[f"distribution_xi_{horizon}m"].reset_index(drop=True)
    pit = pit_values(realized, "student_t", mu, sigma, nu, xi)
    diagnostic = pit_uniformity_diagnostic(pit)
    return pd.DataFrame(
        [
            {
                "horizon": horizon,
                "log_predictive_score": log_predictive_score(realized, "student_t", mu, sigma, nu, xi),
                "crps_approximation": continuous_ranked_probability_score(realized, mu, sigma),
                "quantile_coverage_5_95": quantile_coverage(realized, forecasts[f"p5_return_{horizon}m"], forecasts[f"p95_return_{horizon}m"]),
                "calibration_error": calibration_error(realized, mu),
                **diagnostic,
            }
        ]
    )
