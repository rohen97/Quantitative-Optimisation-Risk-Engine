from __future__ import annotations

import pandas as pd


def build_equity_hedges(portfolio: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "risk_exposure": "Equity drawdown",
                "hedge_type": "Equity-only",
                "hedge_instrument_or_basket": "Defensive dividend basket: Swiss healthcare, utilities, staples",
                "target_weight": 0.05,
                "expected_hedge_effectiveness": "Moderate",
                "trade_off_cost": "Lower upside in risk-on markets",
                "residual_risk": "Market beta remains",
            }
        ]
    )
