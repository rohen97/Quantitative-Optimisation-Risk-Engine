from __future__ import annotations

import pandas as pd


def top_recommendations(scorecard: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return scorecard.head(n)
