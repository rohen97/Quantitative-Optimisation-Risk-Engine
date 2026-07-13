from __future__ import annotations

import pandas as pd


def build_dividend_features(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    data["dividend_safety_score"] = (
        35 * data["dividend_yield"].rank(pct=True)
        + 25 * data["dividend_growth_5y"].rank(pct=True)
        + 25 * (1 - data["payout_ratio"].clip(0, 1))
        + 15 * (1 - data["dividend_cut_flag_3y"])
    )
    return data
