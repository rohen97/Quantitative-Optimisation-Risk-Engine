from __future__ import annotations

import pandas as pd


def map_entities(documents: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    return documents.merge(universe[["security_id", "ticker", "company_name"]], on="ticker", how="left")
