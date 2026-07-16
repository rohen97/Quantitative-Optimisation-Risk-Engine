from __future__ import annotations

import pandas as pd


def build_institutional_hedges(stress_report: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build optional institutional hedge placeholders without pricing derivatives."""
    stress = stress_report if stress_report is not None else pd.DataFrame()
    worst = stress.iloc[0]["scenario_name"] if not stress.empty else "portfolio_tail_loss"
    return pd.DataFrame(
        [
            {
                "hedge_id": "INST001",
                "risk_exposure": "Portfolio tail loss",
                "scenario_name": worst,
                "hedge_category": "optional_institutional",
                "hedge_type": "index_hedge_placeholder",
                "hedge_instrument_or_basket": "Index ETF/future overlay or protective put spread",
                "target_weight_or_notional": "Optional; size after mandate approval",
                "expected_hedge_effectiveness": "High if implemented",
                "estimated_cost_or_tradeoff": "Premium, carry cost, basis risk",
                "residual_risk": "Country, currency and single-name basis risk",
                "priority": "Medium",
                "implementation_complexity": "High",
                "hedge_commentary": "Optional only; no derivatives pricing or execution data is implemented.",
            },
            {
                "hedge_id": "INST002",
                "risk_exposure": "FX shock",
                "scenario_name": "fx_shock",
                "hedge_category": "optional_institutional",
                "hedge_type": "fx_forward_placeholder",
                "hedge_instrument_or_basket": "EUR/GBP/CNY exposure hedge placeholder",
                "target_weight_or_notional": "Optional; based on currency exposure",
                "expected_hedge_effectiveness": "Moderate",
                "estimated_cost_or_tradeoff": "Forward points and operational complexity",
                "residual_risk": "Equity loss remains after currency hedge",
                "priority": "Medium",
                "implementation_complexity": "High",
                "hedge_commentary": "Optional institutional FX hedge placeholder.",
            },
        ]
    )
