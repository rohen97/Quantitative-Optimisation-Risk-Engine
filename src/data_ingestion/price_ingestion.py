from __future__ import annotations

import pandas as pd

from src.data_ingestion.alpaca_adapter import AlpacaMarketDataAdapter
from src.data_ingestion.mock_data import generate_mock_prices
from src.utils.env import env_flag, get_env


def load_prices(universe: pd.DataFrame, use_mock: bool | None = None) -> pd.DataFrame:
    """Load model-ready daily prices from mock data or an enabled vendor adapter."""
    if use_mock is None:
        use_mock = env_flag("USE_MOCK_DATA", True)
    if use_mock:
        return generate_mock_prices(universe)
    provider = (get_env("DATA_PROVIDER", "alpaca") or "alpaca").lower()
    if provider == "alpaca":
        adapter = AlpacaMarketDataAdapter()
        return adapter.load_daily_bars(universe["ticker"].dropna().astype(str).unique().tolist())
    raise NotImplementedError(f"Unsupported price data provider: {provider}")
