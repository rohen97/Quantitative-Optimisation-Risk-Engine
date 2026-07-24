from __future__ import annotations

import pandas as pd

from src.data.normalisers import normalise_macro_vintages


def ingest_macro(raw_macro: pd.DataFrame, source: str = "mock") -> pd.DataFrame:
    return normalise_macro_vintages(raw_macro, source=source)
