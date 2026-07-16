from __future__ import annotations

import pandas as pd


def build_scenario_library(regime_summary: pd.DataFrame | None = None) -> list[dict]:
    """Build deterministic stress scenario definitions for mock risk testing."""
    scenarios = [
        {"scenario_name": "global_risk_off", "base_shock": -0.20, "beta_extra": -0.10, "liquidity_extra": -0.05},
        {"scenario_name": "crisis_high_chaos", "base_shock": -0.25, "chaos_extra": -0.10, "low_quality_extra": -0.10, "liquidity_extra": -0.075},
        {
            "scenario_name": "europe_recession",
            "base_shock": 0.0,
            "region_shocks": {"DACH": -0.20, "EU ex-DACH": -0.20},
            "sector_shocks": {"Industrials": -0.20, "Consumer Discretionary": -0.20, "Healthcare": -0.08, "Consumer Staples": -0.08, "Utilities": -0.08},
            "currency_shocks": {"EUR": -0.08},
        },
        {
            "scenario_name": "china_policy_stress",
            "base_shock": 0.0,
            "region_shocks": {"Mainland China": -0.25, "Hong Kong": -0.25},
            "regulatory_extra": -0.10,
            "property_extra": -0.15,
        },
        {"scenario_name": "uk_rate_shock", "base_shock": 0.0, "region_shocks": {"UK": -0.12}, "currency_shocks": {"GBP": -0.05}, "debt_extra": -0.08},
        {"scenario_name": "inflation_shock", "base_shock": -0.05, "sector_shocks": {"Technology": -0.20, "Energy": 0.05, "Materials": 0.05, "Financials": 0.05}, "debt_extra": -0.10},
        {"scenario_name": "credit_stress", "base_shock": -0.05, "debt_extra": -0.20, "credit_extra": -0.20},
        {"scenario_name": "dividend_cut_shock", "base_shock": -0.05, "dividend_cut_extra": -0.20, "payout_extra": -0.10},
        {"scenario_name": "liquidity_shock", "base_shock": -0.05, "low_adv_extra": -0.15, "liquidity_extra": -0.25},
        {"scenario_name": "meta_wolf_shock", "base_shock": -0.25, "meta_wolf_extra": -0.15},
        {"scenario_name": "fx_shock", "base_shock": 0.0, "currency_shocks": {"EUR": -0.08, "GBP": -0.07, "CNY": -0.06, "HKD": -0.03, "CHF": 0.05}},
        {"scenario_name": "correlation_spike", "base_shock": -0.08, "tail_risk_extra": -0.08},
    ]
    if regime_summary is not None and not regime_summary.empty:
        dominant = str(regime_summary.iloc[0].get("dominant_regime", ""))
        for scenario in scenarios:
            scenario["current_regime_match"] = scenario["scenario_name"] == dominant
    return scenarios
