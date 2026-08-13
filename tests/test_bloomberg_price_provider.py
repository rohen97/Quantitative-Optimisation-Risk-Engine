from __future__ import annotations

import pandas as pd

from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.provider_registry import load_data_source_registry


def test_bloomberg_provider_is_optional_and_credentialless(monkeypatch):
    monkeypatch.delenv("BLOOMBERG_DESKTOP_ENABLED", raising=False)
    registry = load_data_source_registry()
    provider = registry.providers["bloomberg"]
    assert provider.credential_env is None
    assert provider.availability_env == "BLOOMBERG_DESKTOP_ENABLED"
    assert provider.available is False
    monkeypatch.setenv("BLOOMBERG_DESKTOP_ENABLED", "false")
    assert provider.available is False
    monkeypatch.setenv("BLOOMBERG_DESKTOP_ENABLED", "true")
    assert provider.available is True


def test_price_loader_maps_bloomberg_symbol_back_to_security_id(monkeypatch):
    class FakeBloombergAdapter:
        def load_daily_bars(self, symbols):
            assert symbols == ["700 HK Equity"]
            return pd.DataFrame(
                {
                    "date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
                    "ticker": ["700 HK Equity", "700 HK Equity"],
                    "open": [410.0, 414.0],
                    "high": [418.0, 417.0],
                    "low": [408.0, 410.0],
                    "close": [416.0, 414.2],
                    "adjusted_close": [416.0, 414.2],
                    "volume": [20_733_037.0, 16_843_241.0],
                    "return": [0.0, (414.2 / 416.0) - 1.0],
                    "source": ["bloomberg", "bloomberg"],
                }
            )

    monkeypatch.setenv("BLOOMBERG_DESKTOP_ENABLED", "true")
    monkeypatch.setenv("DATA_PRICE_PROVIDERS", "bloomberg")
    monkeypatch.setenv("USE_ALL_AVAILABLE_DATA_SOURCES", "true")
    monkeypatch.setattr(
        "src.data_ingestion.price_ingestion.BloombergDesktopAdapter",
        FakeBloombergAdapter,
    )
    universe = pd.DataFrame(
        {
            "ticker": ["0700.HK"],
            "bloomberg_ticker": ["700 HK Equity"],
            "currency": ["HKD"],
        }
    )
    prices = load_prices(universe, use_mock=False)
    assert prices["ticker"].eq("0700.HK").all()
    assert prices["source"].eq("bloomberg").all()
    assert prices["close"].tolist() == [416.0, 414.2]
