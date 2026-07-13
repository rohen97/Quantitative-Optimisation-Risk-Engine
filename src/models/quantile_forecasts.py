from __future__ import annotations

import pandas as pd


def conformal_placeholder(forecasts: pd.DataFrame) -> pd.DataFrame:
    return forecasts.copy()
