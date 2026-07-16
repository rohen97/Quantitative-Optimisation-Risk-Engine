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
    data["regime_weight_adjustment"] = _series(data, "regime_weight_adjustment", 0).fillna(0)
    data["regime_review_required_flag"] = _series(data, "regime_review_required_flag", False).fillna(False)
    data["regime_exclusion_flag"] = _series(data, "regime_exclusion_flag", False).fillna(False)
    data["regime_risk_score"] = _series(data, "regime_risk_score", neutral).fillna(neutral)
    data["regime_deterioration_probability"] = _series(data, "regime_deterioration_probability", 0).fillna(0)
    data["dominant_regime"] = _series(data, "dominant_regime", "steady_state_low_chaos").fillna("steady_state_low_chaos")
    data["ml_expected_risk_adjusted_return_score"] = _series(data, "ml_expected_risk_adjusted_return_score", neutral).fillna(neutral)
    data["sentiment_alt_signal_score"] = _series(data, "sentiment_alt_signal_score", neutral).fillna(neutral)
    data["sentiment_alt_data_score"] = _series(data, "sentiment_alt_data_score", data["sentiment_alt_signal_score"]).fillna(neutral)
    data["sentiment_alt_signal_score"] = data["sentiment_alt_data_score"]
    data["average_daily_value_usd"] = _series(data, "average_daily_value_usd", 0).fillna(_series(data, "avg_daily_traded_value_usd", 0))
    data["regulatory_risk_score"] = _series(data, "regulatory_risk_score", 0).fillna(0)
    data["credit_stress_score"] = _series(data, "credit_stress_score", 0).fillna(0)
    data["liquidity_stress_score"] = _series(data, "liquidity_stress_score", 0).fillna(0)
    data["negative_news_intensity"] = _series(data, "negative_news_intensity", 0).fillna(0)
    data["governance_red_flag_count"] = _series(data, "governance_red_flag_count", 0).fillna(0)
    data["alt_data_review_required_flag"] = _series(data, "alt_data_review_required_flag", False).fillna(False)
    data["alt_data_exclusion_flag"] = _series(data, "alt_data_exclusion_flag", False).fillna(False)
    data["narrative_reframing_score"] = _series(data, "narrative_reframing_score", neutral).fillna(neutral)
    data["risk_reframing_score"] = _series(data, "risk_reframing_score", neutral).fillna(neutral)
    data["positive_reframing_score"] = _series(data, "positive_reframing_score", neutral).fillna(neutral)
    data["distress_similarity_score"] = _series(data, "distress_similarity_score", neutral).fillna(neutral)
    data["dividend_risk_similarity_score"] = _series(data, "dividend_risk_similarity_score", neutral).fillna(neutral)
    data["credit_stress_similarity_score"] = _series(data, "credit_stress_similarity_score", neutral).fillna(neutral)
    data["governance_risk_similarity_score"] = _series(data, "governance_risk_similarity_score", neutral).fillna(neutral)
    data["regulatory_risk_similarity_score"] = _series(data, "regulatory_risk_similarity_score", neutral).fillna(neutral)
    data["markov_negative_to_distress_prob"] = _series(data, "markov_negative_to_distress_prob", 0).fillna(0)
    data["reframing_review_required_flag"] = _series(data, "reframing_review_required_flag", False).fillna(False)
    data["reframing_exclusion_flag"] = _series(data, "reframing_exclusion_flag", False).fillna(False)
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
        & (~data["alt_data_exclusion_flag"].astype(bool))
        & (~data["reframing_exclusion_flag"].astype(bool))
        & (~data["regime_exclusion_flag"].astype(bool))
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
    data.loc[data["dividend_risk_similarity_score"] > 85, "final_recommendation_score"] = np.minimum(data["final_recommendation_score"], 64)
    data.loc[data["risk_reframing_score"] > 80, "final_recommendation_score"] = np.minimum(data["final_recommendation_score"], 64)
    data.loc[data["regime_review_required_flag"].astype(bool), "final_recommendation_score"] = np.minimum(data["final_recommendation_score"], 64)
    data.loc[data["regulatory_risk_score"] > 85, "passes_hard_filters"] = False
    data.loc[data["credit_stress_score"] > 85, "passes_hard_filters"] = False
    data.loc[data["regulatory_risk_similarity_score"] > 85, "passes_hard_filters"] = False
    data["recommendation"] = [classify_score(s, p) for s, p in zip(data["final_recommendation_score"], data["passes_hard_filters"])]
    max_weight = (risk_limits or {}).get("maximum_single_name_weight", (risk_limits or {}).get("max_new_position_weight", 0.05))
    data["target_weight"] = np.where(
        data["recommendation"].str.contains("Buy"),
        (data["final_recommendation_score"] / 100 * max_weight).clip(0.01, max_weight),
        0.0,
    )
    data.loc[data["liquidity_stress_score"] > 80, "target_weight"] = data["target_weight"].clip(upper=0.01)
    data.loc[data["negative_news_intensity"] > 3, "target_weight"] *= 0.5
    data.loc[(data["credit_stress_similarity_score"] > 85) | (data["markov_negative_to_distress_prob"] > 0.35), "target_weight"] = data[
        "target_weight"
    ].clip(upper=0.01)
    cyclical_or_levered = data["sector"].isin(["Industrials", "Consumer Discretionary", "Technology", "Materials", "Energy"]) | (
        data["net_debt_to_ebitda"].fillna(0) > 3
    ) | (data["liquidity_score"].fillna(50) < 45)
    data.loc[(data["regime_deterioration_probability"] > 0.70) & cyclical_or_levered, "target_weight"] *= 0.5
    data["target_weight"] = (data["target_weight"] + data["regime_weight_adjustment"].clip(-0.03, 0.03)).clip(lower=0)
    data.loc[~data["recommendation"].str.contains("Buy"), "target_weight"] = 0.0
    data["risk_management_flags"] = ""
    data.loc[data["dividend_risk_score"] > 80, "risk_management_flags"] += "dividend_risk;"
    data.loc[data["regulatory_risk_score"] > 85, "risk_management_flags"] += "regulatory_risk;"
    data.loc[data["liquidity_stress_score"] > 80, "risk_management_flags"] += "liquidity_stress;"
    data.loc[data["alt_data_review_required_flag"].astype(bool), "risk_management_flags"] += "alt_data_review;"
    data.loc[data["governance_red_flag_count"] > 2, "risk_management_flags"] += "governance_review;"
    data.loc[data["reframing_review_required_flag"].astype(bool), "risk_management_flags"] += "narrative_review;"
    data.loc[data["reframing_exclusion_flag"].astype(bool), "risk_management_flags"] += "narrative_exclusion;"
    data.loc[data["regime_review_required_flag"].astype(bool), "risk_management_flags"] += "regime_review;"
    data.loc[data["regime_exclusion_flag"].astype(bool), "risk_management_flags"] += "regime_exclusion;"
    data.loc[data["regime_deterioration_probability"] > 0.70, "risk_management_flags"] += "regime_deterioration;"
    return data.sort_values("final_recommendation_score", ascending=False).reset_index(drop=True)
