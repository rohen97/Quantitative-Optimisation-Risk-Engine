from __future__ import annotations

import pandas as pd


def income_adjusted_score(frame: pd.DataFrame) -> pd.Series:
    return frame["final_recommendation_score"] + 100 * frame["dividend_yield"]
