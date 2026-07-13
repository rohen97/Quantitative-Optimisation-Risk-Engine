from __future__ import annotations

import pandas as pd


def build_financial_features(fundamentals: pd.DataFrame) -> pd.DataFrame:
    data = fundamentals.copy()
    data["cash_flow_quality_score"] = (
        35 * data["free_cash_flow_yield"].rank(pct=True)
        + 30 * data["fcf_margin"].rank(pct=True)
        + 20 * data["fcf_stability"] / 100
        + 15 * data["cfo_to_net_income"].clip(0, 1.5) / 1.5
    )
    data["balance_sheet_strength_score"] = (
        45 * (1 - (data["net_debt_to_ebitda"] / 5).clip(0, 1))
        + 35 * (data["interest_coverage"] / 20).clip(0, 1)
        + 20 * data["roic"].rank(pct=True)
    )
    return data
