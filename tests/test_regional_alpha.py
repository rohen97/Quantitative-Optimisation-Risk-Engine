from __future__ import annotations

import pandas as pd

from src.models.regional_alpha import RegionalAlphaSettings, add_regional_alpha_signals


def _scorecard() -> pd.DataFrame:
    rows = []
    for region, return_offset in (("US", 0.10), ("UK", 0.02)):
        for index in range(6):
            rows.append(
                {
                    "security_id": f"{region}-{index}",
                    "region": region,
                    "sector": "Industrials",
                    "currency": "USD" if region == "US" else "GBP",
                    "market_cap_usd": 1_000_000_000 * (index + 1),
                    "average_daily_value_usd": 50_000_000,
                    "expected_total_return_12m": return_offset + index * 0.01,
                    "momentum_6m": index * 0.01,
                    "valuation_score": 40 + index,
                    "cash_flow_quality_score": 50 + index,
                    "balance_sheet_strength_score": 55 + index,
                    "dividend_safety_score": 60 + index,
                    "expected_volatility_12m": 0.30 - index * 0.01,
                    "cvar_5_12m": -0.25 + index * 0.01,
                    "final_recommendation_score": 60 + index,
                    "current_weight": 0.0,
                }
            )
    return pd.DataFrame(rows)


def test_regional_alpha_compares_names_within_their_regional_opportunity_set():
    result = add_regional_alpha_signals(_scorecard())

    us_best = result.loc[result["security_id"].eq("US-5")].iloc[0]
    uk_best = result.loc[result["security_id"].eq("UK-5")].iloc[0]
    assert us_best["regional_alpha_score"] == uk_best["regional_alpha_score"]
    assert us_best["benchmark_relative_expected_return_12m"] > 0
    assert uk_best["benchmark_relative_expected_return_12m"] > 0


def test_regional_alpha_penalises_expensive_entries_and_rewards_retention():
    frame = _scorecard().iloc[:6].copy()
    frame.loc[0, "average_daily_value_usd"] = 100_000
    frame.loc[1, "current_weight"] = 0.05
    frame.loc[1, "expected_total_return_12m"] = frame.loc[0, "expected_total_return_12m"]
    settings = RegionalAlphaSettings(
        minimum_peer_count=2,
        portfolio_nav_usd=100_000_000,
        assumed_position_weight=0.05,
    )

    result = add_regional_alpha_signals(frame, settings).set_index("security_id")

    assert result.loc["US-0", "estimated_entry_cost_fraction"] > result.loc[
        "US-1", "estimated_entry_cost_fraction"
    ]
    assert result.loc["US-1", "regional_alpha_retention_bonus"] > 0
    assert result.loc["US-1", "regional_alpha_selection_utility"] > result.loc[
        "US-0", "regional_alpha_selection_utility"
    ]
