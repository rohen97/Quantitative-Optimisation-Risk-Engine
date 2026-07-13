from __future__ import annotations

import pandas as pd


def run_stress_tests(portfolio: pd.DataFrame) -> pd.DataFrame:
    scenarios = {
        "global_risk_off": {"all": -0.20},
        "europe_recession": {"DACH": -0.20, "EUR": -0.08},
        "china_policy_property_stress": {"Mainland China": -0.25, "Hong Kong": -0.25},
        "india_fx_stress": {"India": -0.15, "INR": -0.08},
        "financial_stress": {"Financials": -0.20},
        "dividend_cut_shock": {"all": -0.05},
        "meta_wolf_shock": {"all": -0.25},
    }
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
