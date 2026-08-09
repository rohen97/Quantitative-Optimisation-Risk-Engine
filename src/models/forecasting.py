from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.dividend_risk_model import estimate_dividend_cut_probability
from src.models.distributional_forecasting import build_distributional_forecasts
from src.models.drawdown_model import estimate_drawdown_probability
from src.models.forecast_features import build_forecast_feature_matrix
from src.models.quantile_forecasts import build_return_distribution_forecasts
from src.models.targets import HORIZONS_MONTHS


def _series(data: pd.DataFrame, column: str, default: float | str) -> pd.Series:
    if column in data:
        return data[column]
    return pd.Series(default, index=data.index)


def _regime_adjustment(data: pd.DataFrame) -> pd.Series:
    regime = _series(data, "dominant_regime", "steady_state_low_chaos").astype(str)
    sector = _series(data, "sector", "").astype(str)
    region = _series(data, "region", "").astype(str)
    beta = _series(data, "beta_local_market", 1.0).fillna(1.0)
    leverage = _series(data, "net_debt_to_ebitda", 2.0).fillna(2.0)
    liquidity = _series(data, "liquidity_score", 50).fillna(50)
    interest = _series(data, "interest_coverage", 6).fillna(6)
    adjustment = pd.Series(0.0, index=data.index)
    cyclical = sector.isin(["Industrials", "Consumer Discretionary", "Technology", "Materials", "Energy"])
    adjustment -= np.where(regime.eq("crisis_high_chaos") & ((beta > 1.1) | (leverage > 3) | (liquidity < 45) | cyclical), 0.05, 0.0)
    adjustment += np.where(regime.eq("inflation_pressure") & sector.isin(["Financials", "Energy", "Materials"]), 0.025, 0.0)
    adjustment -= np.where(regime.eq("inflation_pressure") & (leverage > 3), 0.025, 0.0)
    adjustment -= np.where(regime.eq("europe_recession") & region.isin(["DACH", "EU ex-DACH"]) & cyclical, 0.04, 0.0)
    adjustment -= np.where(regime.eq("china_policy_stress") & region.isin(["Mainland China", "Hong Kong"]), 0.04, 0.0)
    adjustment -= np.where(regime.eq("uk_rate_pressure") & region.eq("UK") & (leverage > 3), 0.03, 0.0)
    adjustment += np.where(regime.eq("uk_rate_pressure") & region.eq("UK") & sector.eq("Financials"), 0.015, 0.0)
    adjustment -= np.where(regime.eq("credit_stress") & ((leverage > 3) | (interest < 4)), 0.045, 0.0)
    return adjustment


def build_ml_forecast_features(features: pd.DataFrame, regime_dashboard: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    """Forecast total-return distributions and risk probabilities from point-in-time features."""
    identifiers, _, _ = build_forecast_feature_matrix(features)
    data = features.copy()
    dividend = estimate_dividend_cut_probability(data)
    drawdown = estimate_drawdown_probability(data, regime_dashboard)
    dividend_yield = _series(data, "dividend_yield", 0.03).fillna(0.03)
    momentum = _series(data, "momentum_6m", 0.0).fillna(0.0).clip(-0.4, 0.5)
    valuation = (_series(data, "valuation_score", 50).fillna(50) - 50) / 100
    quality = (_series(data, "cash_flow_quality_score", 50).fillna(50) - 50) / 120
    balance = (_series(data, "balance_sheet_strength_score", 50).fillna(50) - 50) / 180
    sentiment = (_series(data, "sentiment_alt_signal_score", 50).fillna(50) - 50) / 180
    regime_score = (_series(data, "regime_suitability_score", 50).fillna(50) - 50) / 160
    base_return = (dividend_yield + 0.22 * momentum + valuation + quality + balance + sentiment + regime_score + _regime_adjustment(data)).clip(-0.25, 0.35)
    vol_annual = _series(data, "volatility_1y", 0.20).fillna(0.20).clip(0.05, 0.65)
    uncertainty = (
        35
        + 35 * _series(data, "regime_deterioration_probability", 0).fillna(0).clip(0, 1)
        + 20 * dividend["dividend_cut_probability"].clip(0, 1)
        + 20 * drawdown["large_drawdown_probability_12m"].clip(0, 1)
        + 15 * (vol_annual / 0.45).clip(0, 1)
    ).clip(0, 100)
    wide = identifiers.copy()
    for months in HORIZONS_MONTHS:
        scale = months / 12
        wide[f"expected_price_return_{months}m"] = ((base_return - dividend_yield) * scale).clip(-0.40, 0.45)
        wide[f"expected_dividend_return_{months}m"] = (dividend_yield * scale).clip(0, 0.12)
        wide[f"expected_total_return_{months}m"] = wide[f"expected_price_return_{months}m"] + wide[f"expected_dividend_return_{months}m"]
        wide[f"expected_volatility_{months}m"] = vol_annual * np.sqrt(scale)
        wide[f"expected_max_drawdown_{months}m"] = drawdown[f"expected_max_drawdown_{months}m"]
    wide["dividend_cut_probability"] = dividend["dividend_cut_probability"]
    wide["large_drawdown_probability_12m"] = drawdown["large_drawdown_probability_12m"]
    wide["forecast_uncertainty_score"] = uncertainty
    wide["regime_suitability_score"] = _series(data, "regime_suitability_score", 50).fillna(50)
    wide["dominant_regime"] = _series(data, "dominant_regime", "steady_state_low_chaos")
    distributional = build_distributional_forecasts(data, wide, mode="student_t_parametric")
    dist_columns = [col for col in distributional.columns if col not in wide.columns or col == "ticker"]
    wide = wide.merge(distributional[dist_columns], on="ticker", how="left")
    for months in HORIZONS_MONTHS:
        wide[f"p5_return_{months}m"] = wide[f"p5_return_{months}m"]
        wide[f"p50_return_{months}m"] = wide[f"p50_return_{months}m"]
        wide[f"p95_return_{months}m"] = wide[f"p95_return_{months}m"]
    wide["distribution_family"] = wide["distribution_name_12m"]
    wide["distribution_degrees_of_freedom"] = wide["distribution_nu_12m"]
    wide["distribution_skewness"] = wide["distribution_xi_12m"]
    distribution = build_return_distribution_forecasts(wide)
    distribution_update = distribution.drop(columns=[col for col in ["security_id", "company_name"] if col in distribution], errors="ignore")
    wide = wide.drop(columns=[col for col in distribution_update.columns if col in wide.columns and col != "ticker"], errors="ignore").merge(distribution_update, on="ticker", how="left")
    wide = wide.copy()
    raw_score = (
        50
        + 150 * wide["expected_total_return_12m"]
        - 90 * wide["expected_volatility_12m"]
        - 40 * wide["large_drawdown_probability_12m"]
        - 35 * wide["dividend_cut_probability"]
        + 0.20 * wide["regime_suitability_score"]
        - 0.20 * wide["forecast_uncertainty_score"]
    )
    wide["ml_expected_risk_adjusted_score"] = raw_score.clip(0, 100)
    wide["ml_expected_risk_adjusted_return_score"] = wide["ml_expected_risk_adjusted_score"]
    horizon_outputs = {}
    for months in HORIZONS_MONTHS:
        horizon = identifiers.copy()
        horizon["horizon"] = f"{months}m"
        horizon["horizon_months"] = months
        horizon["expected_total_return"] = wide[f"expected_total_return_{months}m"]
        horizon["expected_price_return"] = wide[f"expected_price_return_{months}m"]
        horizon["expected_dividend_return"] = wide[f"expected_dividend_return_{months}m"]
        horizon["expected_volatility"] = wide[f"expected_volatility_{months}m"]
        horizon["expected_max_drawdown"] = wide[f"expected_max_drawdown_{months}m"]
        horizon["p5_return"] = wide[f"p5_return_{months}m"]
        horizon["p50_return"] = wide[f"p50_return_{months}m"]
        horizon["p95_return"] = wide[f"p95_return_{months}m"]
        horizon["var_5"] = horizon["p5_return"]
        horizon["var_1"] = wide[f"var_1_{months}m"]
        horizon["cvar_5"] = wide[f"cvar_5_{months}m"]
        horizon["cvar_1"] = wide[f"cvar_1_{months}m"]
        horizon["expected_shortfall_5"] = wide[f"expected_shortfall_5_{months}m"]
        horizon["expected_shortfall_1"] = wide[f"expected_shortfall_1_{months}m"]
        horizon["dividend_cut_probability"] = wide["dividend_cut_probability"]
        horizon["large_drawdown_probability"] = drawdown[f"large_drawdown_probability_{months}m"]
        horizon["ml_expected_risk_adjusted_score"] = wide["ml_expected_risk_adjusted_score"]
        horizon["forecast_uncertainty_score"] = wide["forecast_uncertainty_score"]
        horizon["dominant_regime"] = wide["dominant_regime"]
        horizon["regime_suitability_score"] = wide["regime_suitability_score"]
        horizon["distribution_name"] = wide[f"distribution_name_{months}m"]
        horizon["distribution_mu"] = wide[f"distribution_mu_{months}m"]
        horizon["distribution_sigma"] = wide[f"distribution_sigma_{months}m"]
        horizon["distribution_nu"] = wide[f"distribution_nu_{months}m"]
        horizon["distribution_xi"] = wide[f"distribution_xi_{months}m"]
        horizon["tail_risk_score"] = wide[f"tail_risk_score_{months}m"]
        horizon["skewness_risk_score"] = wide[f"skewness_risk_score_{months}m"]
        horizon["distribution_model_confidence"] = wide[f"distribution_model_confidence_{months}m"]
        horizon["distribution_family"] = wide["distribution_family"]
        horizon["distribution_degrees_of_freedom"] = wide["distribution_degrees_of_freedom"]
        horizon["distribution_skewness"] = wide["distribution_skewness"]
        horizon["forecast_commentary"] = "Deterministic mock ML forecast uses quality, valuation, income, risk, sentiment, narrative and regime inputs."
        horizon_outputs[f"ml_forecasts_{months}m"] = horizon
    return {
        "ml_features": wide,
        "return_distribution_forecasts": distribution,
        "dividend_cut_probability": dividend,
        "drawdown_probability": drawdown,
        **horizon_outputs,
    }


def generate_mock_forecasts(scorecard: pd.DataFrame, horizon_months: int) -> pd.DataFrame:
    """Backward-compatible recommendation forecast output using ML columns when present."""
    data = scorecard.copy()
    if f"expected_total_return_{horizon_months}m" in data:
        data["expected_total_return"] = data[f"expected_total_return_{horizon_months}m"]
        data["expected_volatility"] = data[f"expected_volatility_{horizon_months}m"]
        data["risk_adjusted_return"] = data["expected_total_return"] / data["expected_volatility"].clip(lower=0.01)
        data["var_5"] = data.get(f"p5_return_{horizon_months}m", data["expected_total_return"] - 1.65 * data["expected_volatility"])
        data["var_1"] = data.get(f"var_1_{horizon_months}m", data["var_5"] - 0.35 * data["expected_volatility"])
        data["cvar_5"] = data.get(f"cvar_5_{horizon_months}m", data["var_5"] - 0.25 * data["expected_volatility"])
        data["cvar_1"] = data.get(f"cvar_1_{horizon_months}m", data["var_1"] - 0.25 * data["expected_volatility"])
        data["p5_return"] = data["var_5"]
        data["p50_return"] = data.get(f"p50_return_{horizon_months}m", data["expected_total_return"])
        data["p95_return"] = data.get(f"p95_return_{horizon_months}m", data["expected_total_return"] + 1.65 * data["expected_volatility"])
        data["horizon_months"] = horizon_months
        return data
    horizon_scale = horizon_months / 12
    data["expected_total_return"] = (data["dividend_yield"] + data["momentum_6m"].clip(-0.2, 0.3) * 0.4) * horizon_scale
    data["expected_volatility"] = data["volatility_1y"] * horizon_scale**0.5
    data["risk_adjusted_return"] = data["expected_total_return"] / data["expected_volatility"].clip(lower=0.01)
    data["var_5"] = data["expected_total_return"] - 1.65 * data["expected_volatility"]
    data["cvar_5"] = data["expected_total_return"] - 2.05 * data["expected_volatility"]
    data["p5_return"] = data["var_5"]
    data["p50_return"] = data["expected_total_return"]
    data["p95_return"] = data["expected_total_return"] + 1.65 * data["expected_volatility"]
    data["horizon_months"] = horizon_months
    return data
