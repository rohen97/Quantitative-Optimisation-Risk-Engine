from __future__ import annotations

import pandas as pd


def check_weight_caps(portfolio: pd.DataFrame, max_weight: float = 0.05) -> bool:
    return bool((portfolio["target_weight"] <= max_weight + 1e-12).all())
