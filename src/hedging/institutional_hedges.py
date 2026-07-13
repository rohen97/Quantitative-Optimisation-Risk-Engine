from __future__ import annotations

import pandas as pd


def build_institutional_hedges() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "risk_exposure": "Portfolio tail loss",
                "hedge_type": "Optional institutional",
                "hedge_instrument_or_basket": "Index ETF/future overlay or protective put spread",
                "target_weight": 0.0,
                "expected_hedge_effectiveness": "High if implemented",
                "trade_off_cost": "Premium, basis risk, operational complexity",
                "residual_risk": "Country and FX basis risk",
            }
        ]
    )
