import json

import pytest

from src.data_ingestion.alpaca_adapter import AlpacaConfigurationError, AlpacaMarketDataAdapter
from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.universe import build_universe


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_alpaca_config_requires_credentials(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY_ID", raising=False)
    monkeypatch.delenv("ALPACA_API_SECRET_KEY", raising=False)
    monkeypatch.setattr("src.data_ingestion.alpaca_adapter.get_env", lambda name, default=None: "" if name.startswith("ALPACA_API") else default)
    with pytest.raises(AlpacaConfigurationError):
        AlpacaMarketDataAdapter()


def test_alpaca_account_request_uses_auth_headers(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["headers"] = dict(request.header_items())
        return _Response({"id": "acct_123", "status": "ACTIVE"})

    monkeypatch.setattr("src.data_ingestion.alpaca_adapter.urlopen", fake_urlopen)
    monkeypatch.setenv("ALPACA_API_KEY_ID", "key")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "secret")
    account = AlpacaMarketDataAdapter().fetch_account()
    assert account["status"] == "ACTIVE"
    headers = {key.lower(): value for key, value in captured["headers"].items()}
    assert headers["apca-api-key-id"] == "key"
    assert headers["apca-api-secret-key"] == "secret"


def test_alpaca_daily_bars_normalize_to_price_schema(monkeypatch):
    def fake_urlopen(request, timeout):
        return _Response(
            {
                "bars": {
                    "AAPL": [
                        {"t": "2026-01-02T05:00:00Z", "c": 100.0},
                        {"t": "2026-01-03T05:00:00Z", "c": 110.0},
                    ]
                }
            }
        )

    monkeypatch.setattr("src.data_ingestion.alpaca_adapter.urlopen", fake_urlopen)
    monkeypatch.setenv("ALPACA_API_KEY_ID", "key")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "secret")
    bars = AlpacaMarketDataAdapter().load_daily_bars(["AAPL"])
    assert list(bars.columns) == ["date", "ticker", "close", "return"]
    assert bars["return"].iloc[0] == 0
    assert round(float(bars["return"].iloc[1]), 4) == 0.1


def test_price_loader_defaults_to_mock():
    prices = load_prices(build_universe(n=3), use_mock=True)
    assert {"date", "ticker", "close", "return"}.issubset(prices.columns)
