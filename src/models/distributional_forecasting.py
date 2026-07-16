from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.distributions import distribution_ppf
from src.models.targets import HORIZONS_MONTHS


def fit_distributional_forecaster(features: pd.DataFrame, mode: str = "mock") -> dict[str, object]:
    """Return a lightweight fitted-state placeholder for future CNN/LSTM distributional models."""
    return {
        "mode": mode,
        "default_distribution": "student_t",
        "future_architectures": ["cnn_1d", "lstm"],
        "n_features": int(features.shape[1]),
    }


def predict_distribution_parameters(features: pd.DataFrame, base_forecasts: pd.DataFrame, mode: str = "student_t_parametric") -> pd.DataFrame:
    """Estimate Normal/Student-t/skewed Student-t parameters per stock and horizon."""
    output = base_forecasts[[col for col in ["security_id", "ticker", "company_name"] if col in base_forecasts]].copy()
    drawdown = base_forecasts.get("large_drawdown_probability_12m", pd.Series(0.15, index=base_forecasts.index)).fillna(0.15)
    dividend = base_forecasts.get("dividend_cut_probability", pd.Series(0.15, index=base_forecasts.index)).fillna(0.15)
    distribution = "student_t" if mode != "skewed_student_t_placeholder" else "skewed_student_t_placeholder"
    for months in HORIZONS_MONTHS:
        mu = base_forecasts[f"expected_total_return_{months}m"]
        sigma = base_forecasts[f"expected_volatility_{months}m"].clip(lower=0.0001)
        nu = (14 - 9 * drawdown - 4 * dividend).clip(lower=2.01, upper=30)
        xi = (1 - 0.75 * drawdown - 0.35 * dividend).clip(lower=0.1, upper=10)
        output[f"distribution_name_{months}m"] = distribution
        output[f"distribution_mu_{months}m"] = mu
        output[f"distribution_sigma_{months}m"] = sigma
        output[f"distribution_nu_{months}m"] = nu
        output[f"distribution_xi_{months}m"] = xi
    return output


def derive_distributional_risk_metrics(parameters: pd.DataFrame) -> pd.DataFrame:
    """Derive quantiles, VaR, CVaR, expected shortfall and risk scores from distribution parameters."""
    output = parameters.copy()
    for months in HORIZONS_MONTHS:
        dist = output[f"distribution_name_{months}m"].iloc[0] if len(output) else "student_t"
        mu = output[f"distribution_mu_{months}m"]
        sigma = output[f"distribution_sigma_{months}m"]
        nu = output[f"distribution_nu_{months}m"]
        xi = output[f"distribution_xi_{months}m"]
        p1 = distribution_ppf(dist, 0.01, mu, sigma, nu, xi)
        p5 = distribution_ppf(dist, 0.05, mu, sigma, nu, xi)
        p50 = distribution_ppf(dist, 0.50, mu, sigma, nu, xi)
        p95 = distribution_ppf(dist, 0.95, mu, sigma, nu, xi)
        output[f"p5_return_{months}m"] = p5
        output[f"p50_return_{months}m"] = p50
        output[f"p95_return_{months}m"] = p95
        output[f"var_5_{months}m"] = p5
        output[f"var_1_{months}m"] = p1
        output[f"cvar_5_{months}m"] = p5 - 0.35 * sigma
        output[f"cvar_1_{months}m"] = p1 - 0.55 * sigma
        output[f"expected_shortfall_5_{months}m"] = output[f"cvar_5_{months}m"]
        output[f"expected_shortfall_1_{months}m"] = output[f"cvar_1_{months}m"]
        tail = (100 * ((6 - nu).clip(lower=0) / 4 + (-output[f"cvar_5_{months}m"]).clip(lower=0) / 0.35) / 2).clip(0, 100)
        skew = (100 * (1 - xi).clip(lower=0) / 0.65).clip(0, 100)
        output[f"tail_risk_score_{months}m"] = tail
        output[f"skewness_risk_score_{months}m"] = skew
        output[f"distribution_model_confidence_{months}m"] = (85 - 0.25 * tail - 0.15 * skew).clip(35, 90)
    output["tail_risk_score"] = output["tail_risk_score_12m"]
    output["skewness_risk_score"] = output["skewness_risk_score_12m"]
    output["distribution_model_confidence"] = output["distribution_model_confidence_12m"]
    return output


def build_distributional_forecasts(features: pd.DataFrame, base_forecasts: pd.DataFrame, mode: str = "student_t_parametric") -> pd.DataFrame:
    """Build distributional forecast parameters and derived risk metrics."""
    fit_distributional_forecaster(features, mode=mode)
    parameters = predict_distribution_parameters(features, base_forecasts, mode=mode)
    return derive_distributional_risk_metrics(parameters)
