from __future__ import annotations

import pandas as pd


def _regime_scenario(regime_summary: pd.DataFrame | None) -> tuple[str, dict[str, float]] | None:
    """Map the fused regime dashboard to an additional portfolio stress."""
    if regime_summary is None or regime_summary.empty or "dominant_regime" not in regime_summary:
        return None
    regime = str(regime_summary.iloc[0]["dominant_regime"])
    mapping = {
        "crisis_high_chaos": ("regime_crisis_high_chaos", {"all": -0.28, "Financials": -0.08}),
        "inflation_pressure": ("regime_inflation_pressure", {"all": -0.10, "Utilities": -0.06, "Consumer Staples": -0.04}),
        "europe_recession": ("regime_europe_recession", {"DACH": -0.24, "EU ex-DACH": -0.24, "EUR": -0.08}),
        "china_policy_stress": ("regime_china_policy_stress", {"Mainland China": -0.30, "Hong Kong": -0.24}),
        "uk_rate_pressure": ("regime_uk_rate_pressure", {"UK": -0.20, "GBP": -0.10}),
        "credit_stress": ("regime_credit_stress", {"all": -0.14, "Financials": -0.14}),
        "risk_on_fragile": ("regime_risk_on_fragile", {"all": -0.12, "Technology": -0.08}),
    }
    return mapping.get(regime)


def run_stress_tests(portfolio: pd.DataFrame, regime_summary: pd.DataFrame | None = None) -> pd.DataFrame:
    scenarios = {
        "global_risk_off": {"all": -0.20},
        "europe_recession": {"DACH": -0.20, "EUR": -0.08},
        "china_policy_property_stress": {"Mainland China": -0.25, "Hong Kong": -0.25},
        "uk_rate_fx_stress": {"UK": -0.15, "GBP": -0.08},
        "financial_stress": {"Financials": -0.20},
        "dividend_cut_shock": {"all": -0.05},
        "meta_wolf_shock": {"all": -0.25},
    }
    regime_case = _regime_scenario(regime_summary)
    if regime_case:
        scenarios[regime_case[0]] = regime_case[1]
    rows = []
    for scenario, shocks in scenarios.items():
        shocked = portfolio.copy()
        shocked["shock"] = shocks.get("all", 0.0)
        shocked["shock"] += shocked["region"].map(shocks).fillna(0)
        shocked["shock"] += shocked["currency"].map(shocks).fillna(0)
        shocked["shock"] += shocked["sector"].map(shocks).fillna(0)
        shocked["loss_usd"] = shocked["market_value_usd"] * shocked["shock"]
        rows.append(
            {
                "scenario": scenario,
                "portfolio_loss_usd": float(shocked["loss_usd"].sum()),
                "portfolio_loss_pct": float(shocked["loss_usd"].sum() / shocked["market_value_usd"].sum()),
                "worst_contributing_stock": shocked.sort_values("loss_usd").iloc[0]["ticker"],
                "residual_risk": "High" if shocked["loss_usd"].sum() / shocked["market_value_usd"].sum() < -0.15 else "Moderate",
            }
        )
    return pd.DataFrame(rows)
