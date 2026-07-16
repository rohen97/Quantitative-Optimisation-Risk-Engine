from __future__ import annotations

import pandas as pd


def hedge_need_from_stress(stress_report: pd.DataFrame) -> str:
    return "High" if stress_report["portfolio_loss_pct"].min() < -0.18 else "Moderate"


def regime_hedge_recommendation(regime_summary: pd.DataFrame | None) -> str:
    """Return a conservative hedge overlay based on the fused market regime."""
    if regime_summary is None or regime_summary.empty or "dominant_regime" not in regime_summary:
        return "Maintain baseline index and currency hedges."
    regime = str(regime_summary.iloc[0]["dominant_regime"])
    recommendations = {
        "crisis_high_chaos": "Increase broad equity downside hedges and reduce cyclical beta.",
        "credit_stress": "Prioritize credit spread hedges and financial-sector protection.",
        "europe_recession": "Add Eurozone equity downside hedges and review EUR exposure.",
        "china_policy_stress": "Reduce China/Hong Kong beta and hedge HKD/CNH-sensitive exposures.",
        "uk_rate_pressure": "Review GBP hedge ratio and UK duration-sensitive equities.",
        "inflation_pressure": "Favor inflation-resilient sectors and review rate-sensitive hedges.",
        "risk_on_fragile": "Keep tactical downside protection while allowing selective risk exposure.",
    }
    return recommendations.get(regime, "Maintain baseline index and currency hedges.")
