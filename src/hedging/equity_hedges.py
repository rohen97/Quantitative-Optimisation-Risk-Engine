from __future__ import annotations

import pandas as pd


def build_equity_hedges(stress_report: pd.DataFrame | None = None, portfolio: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build equity-only hedge recommendations from stress losses."""
    stress = stress_report if stress_report is not None else pd.DataFrame()
    rows = []
    severe = stress[stress.get("hedge_required_flag", pd.Series(False, index=stress.index)).fillna(False)] if not stress.empty else pd.DataFrame()
    scenario_names = severe["scenario_name"].tolist() if not severe.empty else ["baseline_defensive_overlay"]
    for idx, scenario in enumerate(scenario_names, start=1):
        if "europe" in scenario:
            basket = "Healthcare, staples, regulated utilities and global exporters"
            commentary = "Reduce DACH/EU cyclicals and add defensive Europe exposure."
        elif "china" in scenario:
            basket = "Cash-rich China/Hong Kong defensives, utilities and telecoms"
            commentary = "Reduce high regulatory-risk China/HK names."
        elif "dividend" in scenario:
            basket = "High dividend-cover, low-payout defensive income basket"
            commentary = "Replace dividend traps with safer dividend cover."
        elif "credit" in scenario:
            basket = "Net-cash, high-interest-cover defensive equities"
            commentary = "Reduce refinancing-risk names."
        else:
            basket = "Low-volatility dividend basket: healthcare, staples, utilities, Swiss defensives"
            commentary = "Add equity-only downside ballast and trim cyclicals."
        rows.append(
            {
                "hedge_id": f"EQH{idx:03d}",
                "risk_exposure": scenario,
                "scenario_name": scenario,
                "hedge_category": "equity_only",
                "hedge_type": "defensive_equity_basket",
                "hedge_instrument_or_basket": basket,
                "target_weight_or_notional": 0.05,
                "expected_hedge_effectiveness": "Moderate",
                "estimated_cost_or_tradeoff": "Lower upside in risk-on markets",
                "residual_risk": "Market beta and FX basis remain",
                "priority": "High" if scenario != "baseline_defensive_overlay" else "Medium",
                "implementation_complexity": "Low",
                "hedge_commentary": commentary,
            }
        )
    return pd.DataFrame(rows)
