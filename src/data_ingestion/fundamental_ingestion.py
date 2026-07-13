from __future__ import annotations

import pandas as pd

from src.data_ingestion.mock_data import generate_mock_fundamentals


def load_fundamentals(universe: pd.DataFrame, use_mock: bool = True) -> pd.DataFrame:
    if not use_mock:
        raise NotImplementedError("Vendor fundamental ingestion will be added behind adapters.")
    return generate_mock_fundamentals(universe)
