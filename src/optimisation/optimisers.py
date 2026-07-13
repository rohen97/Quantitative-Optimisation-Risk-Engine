from __future__ import annotations

import pandas as pd


def equal_weight(candidates: pd.DataFrame, max_weight: float = 0.05) -> pd.Series:
    weight = min(max_weight, 1 / len(candidates)) if len(candidates) else 0
    return pd.Series(weight, index=candidates.index)
