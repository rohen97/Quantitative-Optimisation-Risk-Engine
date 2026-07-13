from __future__ import annotations

import pandas as pd


def build_valuation_features(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    cheapness = (1 - data["pe_ratio"].rank(pct=True)) * 0.4 + (1 - data["pb_ratio"].rank(pct=True)) * 0.25 + (1 - data["ev_ebitda"].rank(pct=True)) * 0.35
    data["valuation_score"] = 100 * cheapness
    data["valuation_percentile"] = cheapness
    return data
