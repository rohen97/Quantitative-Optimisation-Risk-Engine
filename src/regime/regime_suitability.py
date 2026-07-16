from __future__ import annotations

import numpy as np
import pandas as pd


DEFENSIVE_SECTORS = {"Healthcare", "Consumer Staples", "Utilities"}
CYCLICAL_SECTORS = {"Industrials", "Consumer Discretionary", "Technology"}


def build_regime_suitability_scores(
    universe: pd.DataFrame,
    features: pd.DataFrame,
    dashboard: pd.DataFrame,
    neutral_score: float = 50,
) -> pd.DataFrame:
    """Score each stock's suitability under the fused current regime."""
    regime = dashboard.iloc[0]["dominant_regime"]
    data = universe.merge(features, on=["security_id", "ticker"], how="left", suffixes=("", "_feature"))
    for col in ["free_cash_flow_yield", "net_debt_to_ebitda", "volatility_1y", "beta_local_market", "liquidity_score", "dividend_safety_score", "regulatory_risk_score"]:
        if col not in data:
            data[col] = neutral_score
    defensive = data["sector"].isin(DEFENSIVE_SECTORS)
    cyclicals = data["sector"].isin(CYCLICAL_SECTORS)
    low_beta = 100 * (1 - data["beta_local_market"].fillna(1).rank(pct=True))
    low_leverage = 100 * (1 - (data["net_debt_to_ebitda"].fillna(2) / 5).clip(0, 1))
    quality = (data["dividend_safety_score"].fillna(50) + data["liquidity_score"].fillna(50) + low_leverage + low_beta) / 4
    data["crisis_suitability_score"] = (quality + defensive.map({True: 15, False: -10})).clip(0, 100)
    data["steady_state_suitability_score"] = (0.35 * data["dividend_safety_score"].fillna(50) + 0.35 * data["free_cash_flow_yield"].rank(pct=True).fillna(0.5) * 100 + 0.30 * data["liquidity_score"].fillna(50)).clip(0, 100)
    data["inflation_suitability_score"] = (neutral_score + data["sector"].isin({"Financials", "Energy", "Materials", "Industrials"}).map({True: 20, False: -5}) - (data["net_debt_to_ebitda"].fillna(2) * 5)).clip(0, 100)
    data["walking_on_ice_suitability_score"] = (0.55 * quality + 0.45 * data["dividend_safety_score"].fillna(50)).clip(0, 100)
    data["europe_recession_suitability_score"] = (quality + defensive.map({True: 15, False: 0}) - ((data["region"].isin(["DACH", "EU ex-DACH"]) & cyclicals).astype(int) * 25)).clip(0, 100)
    data["china_policy_stress_suitability_score"] = (quality - (data["region"].isin(["Mainland China", "Hong Kong"]).astype(int) * data["regulatory_risk_score"].fillna(0) * 0.35)).clip(0, 100)
    data["uk_rate_pressure_suitability_score"] = (quality + ((data["region"].eq("UK") & data["sector"].eq("Financials")).astype(int) * 15) - ((data["region"].eq("UK") & (data["net_debt_to_ebitda"].fillna(2) > 3)).astype(int) * 25)).clip(0, 100)
    data["credit_stress_suitability_score"] = (quality + low_leverage * 0.25 - (data["net_debt_to_ebitda"].fillna(2) * 6)).clip(0, 100)
    mapping = {
        "crisis_high_chaos": "crisis_suitability_score",
        "inflation_pressure": "inflation_suitability_score",
        "risk_on_fragile": "walking_on_ice_suitability_score",
        "europe_recession": "europe_recession_suitability_score",
        "china_policy_stress": "china_policy_stress_suitability_score",
        "uk_rate_pressure": "uk_rate_pressure_suitability_score",
        "credit_stress": "credit_stress_suitability_score",
        "steady_state_low_chaos": "steady_state_suitability_score",
    }
    selected = mapping.get(regime, "steady_state_suitability_score")
    data["regime_suitability_score"] = data[selected].fillna(neutral_score).clip(0, 100)
    data["regime_weight_adjustment"] = ((data["regime_suitability_score"] - 50) / 1000).clip(-0.03, 0.03)
    data["regime_review_required_flag"] = data["regime_suitability_score"] < 35
    data["regime_exclusion_flag"] = data["regime_suitability_score"] < 20
    data["dominant_regime"] = regime
    data["regime_risk_score"] = dashboard.iloc[0]["regime_risk_score"]
    data["regime_deterioration_probability"] = dashboard.iloc[0]["regime_deterioration_probability"]
    data["regime_commentary"] = "Regime suitability reflects current fused market state and stock risk profile."
    columns = [
        "security_id", "ticker", "sector", "country", "region", "currency", "regime_suitability_score",
        "crisis_suitability_score", "inflation_suitability_score", "steady_state_suitability_score",
        "walking_on_ice_suitability_score", "europe_recession_suitability_score",
        "china_policy_stress_suitability_score", "uk_rate_pressure_suitability_score",
        "credit_stress_suitability_score", "regime_weight_adjustment", "regime_review_required_flag",
        "regime_exclusion_flag", "dominant_regime", "regime_risk_score", "regime_deterioration_probability",
        "regime_commentary",
    ]
    return data[columns]
