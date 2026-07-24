from __future__ import annotations

import pandas as pd

from src.data.normalisers import normalise_fundamentals


def ingest_fundamentals(raw_fundamentals: pd.DataFrame, source: str = "mock") -> pd.DataFrame:
    return normalise_fundamentals(raw_fundamentals, source=source)
