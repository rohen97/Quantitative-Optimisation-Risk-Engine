from __future__ import annotations

import pandas as pd


def build_dividend_frame(fundamentals: pd.DataFrame) -> pd.DataFrame:
    return fundamentals[["ticker", "dividend_yield", "dividend_growth_5y", "payout_ratio", "dividend_cut_flag_3y"]].copy()
