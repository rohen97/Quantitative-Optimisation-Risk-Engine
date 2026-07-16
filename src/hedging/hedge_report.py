from __future__ import annotations

import pandas as pd

from src.hedging.equity_hedges import build_equity_hedges
from src.hedging.hedge_rules import regime_hedge_recommendation
from src.hedging.institutional_hedges import build_institutional_hedges


def build_hedge_recommendations(
    portfolio: pd.DataFrame,
    regime_summary: pd.DataFrame | None = None,
    include_institutional: bool = True,
) -> pd.DataFrame:
    frames = [build_equity_hedges(portfolio)]
    if include_institutional:
        frames.append(build_institutional_hedges())
    regime_overlay = pd.DataFrame(
        [
            {
                "risk_exposure": "Fused market regime",
                "hedge_type": "Regime overlay",
                "hedge_instrument_or_basket": "Portfolio-level index, sector and FX overlay",
                "target_weight": 0.0,
                "expected_hedge_effectiveness": "High" if regime_summary is not None and not regime_summary.empty and regime_summary.iloc[0].get("regime_risk_score", 0) > 70 else "Moderate",
                "trade_off_cost": "May reduce upside or add carry cost",
                "residual_risk": regime_hedge_recommendation(regime_summary),
            }
        ]
    )
    frames.append(regime_overlay)
    return pd.concat(frames, ignore_index=True)
