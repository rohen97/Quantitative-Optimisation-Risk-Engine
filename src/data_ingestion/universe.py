from __future__ import annotations

import pandas as pd

from src.data_ingestion.mock_data import generate_mock_universe


def build_universe(use_mock: bool = True, n: int = 24) -> pd.DataFrame:
    if not use_mock:
        raise NotImplementedError("Non-mock universe adapters are scaffolded for future vendor integrations.")
    return generate_mock_universe(n=n)
