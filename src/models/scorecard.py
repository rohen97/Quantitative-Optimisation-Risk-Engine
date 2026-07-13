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


def apply_hard_filters(features: pd.DataFrame, risk_limits: dict | None = None) -> pd.DataFrame:
    limits = risk_limits or {}
    data = features.copy()
    data["passes_hard_filters"] = (
        (data["market_cap_usd"] >= 1_000_000_000)
        & (data["avg_daily_traded_value_usd"] >= 2_000_000)
        & (data["dividend_yield"] >= 0.015)
        & (data["positive_fcf_years_5"] >= 3)
        & (data["dividend_cut_flag_3y"] == 0)
        & (data["payout_ratio"] <= 0.85)
        & (data["net_debt_to_ebitda"] <= 4.0)
        & (data["liquidity_score"] >= limits.get("min_liquidity_score", 40))
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
    data = apply_hard_filters(features, risk_limits)
    data["final_recommendation_score"] = sum(data[col].fillna(0) * weight for col, weight in SCORE_WEIGHTS.items())
    data.loc[data["dividend_risk_score"] > 80, "final_recommendation_score"] = np.minimum(data["final_recommendation_score"], 64)
    data.loc[data["regulatory_risk_score"] > 85, "passes_hard_filters"] = False
    data.loc[data["credit_stress_score"] > 85, "passes_hard_filters"] = False
    data["recommendation"] = [classify_score(s, p) for s, p in zip(data["final_recommendation_score"], data["passes_hard_filters"])]
    data["target_weight"] = np.where(data["recommendation"].str.contains("Buy"), (data["final_recommendation_score"] / 100 * 0.05).clip(0.01, 0.05), 0.0)
    data.loc[data["liquidity_stress_score"] > 80, "target_weight"] = data["target_weight"].clip(upper=0.01)
    data.loc[data["negative_news_intensity"] > 3, "target_weight"] *= 0.5
    data["risk_management_flags"] = ""
    data.loc[data["dividend_risk_score"] > 80, "risk_management_flags"] += "dividend_risk;"
    data.loc[data["regulatory_risk_score"] > 85, "risk_management_flags"] += "regulatory_risk;"
    data.loc[data["liquidity_stress_score"] > 80, "risk_management_flags"] += "liquidity_stress;"
    return data.sort_values("final_recommendation_score", ascending=False).reset_index(drop=True)
