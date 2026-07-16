from __future__ import annotations

import pandas as pd

from src.hedging.defensive_substitutions import build_defensive_substitution_recommendations
from src.hedging.equity_hedges import build_equity_hedges
from src.hedging.hedge_rules import regime_hedge_recommendation
from src.hedging.institutional_hedges import build_institutional_hedges


def build_hedge_recommendations(
    portfolio: pd.DataFrame,
    regime_summary: pd.DataFrame | None = None,
    stress_report: pd.DataFrame | None = None,
    include_institutional: bool = True,
) -> pd.DataFrame:
    """Build equity-only and optional institutional hedge recommendations."""
    frames = [build_equity_hedges(stress_report, portfolio)]
    if include_institutional:
        frames.append(build_institutional_hedges(stress_report))
    regime = pd.DataFrame(
        [
            {
                "hedge_id": "REGIME001",
                "risk_exposure": "Fused market regime",
                "scenario_name": regime_summary.iloc[0].get("dominant_regime", "unknown") if regime_summary is not None and not regime_summary.empty else "unknown",
                "hedge_category": "equity_only",
                "hedge_type": "regime_overlay",
                "hedge_instrument_or_basket": "Portfolio-level sector, country and cash allocation overlay",
                "target_weight_or_notional": 0.0,
                "expected_hedge_effectiveness": "Moderate",
                "estimated_cost_or_tradeoff": "May reduce upside or add cash drag",
                "residual_risk": regime_hedge_recommendation(regime_summary),
                "priority": "High" if regime_summary is not None and not regime_summary.empty and regime_summary.iloc[0].get("regime_risk_score", 0) > 70 else "Medium",
                "implementation_complexity": "Low",
                "hedge_commentary": "Regime overlay is implemented with equity-only allocation shifts.",
            }
        ]
    )
    frames.append(regime)
    return pd.concat(frames, ignore_index=True)


def build_hedge_outputs(
    portfolio: pd.DataFrame,
    regime_summary: pd.DataFrame | None,
    stress_report: pd.DataFrame,
    candidates: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    hedges = build_hedge_recommendations(portfolio, regime_summary, stress_report)
    substitutions = build_defensive_substitution_recommendations(portfolio, candidates)
    return hedges, substitutions
