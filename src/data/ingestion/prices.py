from __future__ import annotations

import pandas as pd

from src.data.normalisers import normalise_prices


def ingest_prices(raw_prices: pd.DataFrame, source: str = "mock") -> pd.DataFrame:
    return normalise_prices(raw_prices, source=source)
