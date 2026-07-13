from __future__ import annotations

import numpy as np
import pandas as pd

SCORE_WEIGHTS = {
    "dividend_safety_score": 0.18,
    "cash_flow_quality_score": 0.18,
    "balance_sheet_strength_score": 0.14,
    "valuation_score": 0.10,
    "regime_suitability_score": 0.10,
    "ml_expected_risk_adjusted_return_score": 0.10,
    "diversification_benefit_score": 0.08,
    "liquidity_score": 0.05,
    "sentiment_alt_signal_score": 0.07,
}


def _series(data: pd.DataFrame, column: str, default: float | str) -> pd.Series:
    """Return a column as a Series, or a default-filled Series if absent."""
    if column in data.columns:
        return data[column]
    return pd.Series(default, index=data.index)


def apply_hard_filters(features: pd.DataFrame, risk_limits: dict | None = None) -> pd.DataFrame:
    """Apply conservative eligibility filters before scoring."""
    limits = risk_limits or {}
    data = features.copy()
    neutral = limits.get("neutral_placeholder_score", 50)
    data["instrument_type"] = _series(data, "instrument_type", "Equity").fillna("Equity")
    data["listing_status"] = _series(data, "listing_status", "Active").fillna("Active")
    data["regime_suitability_score"] = _series(data, "regime_suitability_score", neutral).fillna(neutral)
    data["ml_expected_risk_adjusted_return_score"] = _series(data, "ml_expected_risk_adjusted_return_score", neutral).fillna(neutral)
    data["sentiment_alt_signal_score"] = _series(data, "sentiment_alt_signal_score", neutral).fillna(neutral)
    data["average_daily_value_usd"] = _series(data, "average_daily_value_usd", 0).fillna(_series(data, "avg_daily_traded_value_usd", 0))
    data["regulatory_risk_score"] = _series(data, "regulatory_risk_score", 0).fillna(0)
    data["credit_stress_score"] = _series(data, "credit_stress_score", 0).fillna(0)
    data["liquidity_stress_score"] = _series(data, "liquidity_stress_score", 0).fillna(0)
    data["negative_news_intensity"] = _series(data, "negative_news_intensity", 0).fillna(0)
    non_financial = ~data["sector"].eq("Financials")
    data["passes_hard_filters"] = (
        data["instrument_type"].eq("Equity")
        & data["listing_status"].eq("Active")
        & (data["market_cap_usd"] >= limits.get("minimum_market_cap_usd", 1_000_000_000))
        & (data["average_daily_value_usd"] >= limits.get("minimum_average_daily_value_usd", 2_000_000))
        & (data["dividend_yield"] >= limits.get("minimum_dividend_yield", 0.015))
        & (data["free_cash_flow"].fillna(1) > 0)
        & (data["payout_ratio"] <= limits.get("maximum_payout_ratio", 0.85))
        & (~non_financial | (data["net_debt_to_ebitda"] <= limits.get("maximum_net_debt_to_ebitda", 4.0)))
        & (data["liquidity_score"] >= limits.get("minimum_liquidity_score", limits.get("min_liquidity_score", 40)))
        & (data["regulatory_risk_score"] <= limits.get("max_regulatory_risk_score", 85))
        & (data["credit_stress_score"] <= limits.get("max_credit_stress_score", 85))
        & (data["incremental_portfolio_cvar"] <= limits.get("max_portfolio_cvar_5", 0.12))
    )
    return data


def classify_score(score: float, passed: bool) -> str:
    if not passed or score < 35:
        return "Exclude"
    if score < 50:
        return "Avoid"
    if score < 65:
        return "Watchlist"
    if score < 80:
        return "Buy / Accumulate"
    return "Strong Buy / Core Income Holding"


def build_scorecard(features: pd.DataFrame, risk_limits: dict | None = None) -> pd.DataFrame:
    """Build conservative stock scorecard with filters, weights and overrides."""
    data = apply_hard_filters(features, risk_limits)
    data["final_recommendation_score"] = sum(data[col].fillna(0) * weight for col, weight in SCORE_WEIGHTS.items())
    data.loc[data["dividend_risk_score"] > 80, "final_recommendation_score"] = np.minimum(data["final_recommendation_score"], 64)
    data.loc[data["regulatory_risk_score"] > 85, "passes_hard_filters"] = False
    data.loc[data["credit_stress_score"] > 85, "passes_hard_filters"] = False
    data["recommendation"] = [classify_score(s, p) for s, p in zip(data["final_recommendation_score"], data["passes_hard_filters"])]
    max_weight = (risk_limits or {}).get("maximum_single_name_weight", (risk_limits or {}).get("max_new_position_weight", 0.05))
    data["target_weight"] = np.where(
        data["recommendation"].str.contains("Buy"),
        (data["final_recommendation_score"] / 100 * max_weight).clip(0.01, max_weight),
        0.0,
    )
    data.loc[data["liquidity_stress_score"] > 80, "target_weight"] = data["target_weight"].clip(upper=0.01)
    data.loc[data["negative_news_intensity"] > 3, "target_weight"] *= 0.5
    data["risk_management_flags"] = ""
    data.loc[data["dividend_risk_score"] > 80, "risk_management_flags"] += "dividend_risk;"
    data.loc[data["regulatory_risk_score"] > 85, "risk_management_flags"] += "regulatory_risk;"
    data.loc[data["liquidity_stress_score"] > 80, "risk_management_flags"] += "liquidity_stress;"
    return data.sort_values("final_recommendation_score", ascending=False).reset_index(drop=True)
