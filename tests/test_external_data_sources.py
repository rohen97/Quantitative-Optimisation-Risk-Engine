from __future__ import annotations

import json

import pandas as pd
import pytest

from src.data_ingestion.external_adapters import (
    AlphaVantageAdapter,
    ChinaDataAdapter,
    EcbAdapter,
    EodhdAdapter,
    FinnhubAdapter,
    FrankfurterAdapter,
    FredAdapter,
    ITickAdapter,
    TickDbAdapter,
)
from src.data_ingestion.http_client import HttpResponse, redact_url
from src.data_ingestion.price_ingestion import _combine_provider_prices, _provider_symbols
from src.data_ingestion.provider_registry import ProviderDefinition, load_data_source_registry
from src.utils.config import load_settings


class FakeClient:
    def __init__(self, payload=None, text: str | None = None) -> None:
        self.payload = payload
        self.raw_text = text
        self.calls: list[tuple[str, dict | None, dict | None]] = []

    def get(self, url, params=None, headers=None):
        self.calls.append((url, params, headers))
        body = self.raw_text.encode("utf-8") if self.raw_text is not None else json.dumps(self.payload).encode("utf-8")
        return HttpResponse(body=body, status=200, headers={}, url=url)


def provider(name: str, base_url: str, credential_env: str | None = None) -> ProviderDefinition:
    return ProviderDefinition(
        name=name,
        enabled=True,
        base_url=base_url,
        credential_env=credential_env,
        secret_env=None,
        asset_classes=("equities", "macro", "fx"),
        regions=("DACH", "EU ex-DACH", "UK", "US", "Mainland China", "Hong Kong"),
        settings={},
    )


def test_registry_covers_every_model_region_with_equity_and_macro_sources():
    registry = load_data_source_registry()
    regions = ("DACH", "EU ex-DACH", "UK", "US", "Mainland China", "Hong Kong")
    assert registry.coverage_gaps(regions, "equities") == ()
    assert registry.coverage_gaps(regions, "macro") == ()
    assert {
        "eodhd",
        "finnhub",
        "alpha_vantage",
        "frankfurter",
        "fred",
        "ecb",
        "china_data",
        "itick",
    }.issubset(registry.providers)


def test_central_settings_load_data_source_configuration():
    settings = load_settings()
    assert settings["data_sources"]["policy"]["use_all_available"] is True
    assert "frankfurter" in settings["data_sources"]["providers"]


def test_eodhd_daily_bars_are_normalised(monkeypatch):
    monkeypatch.setattr("src.data_ingestion.external_adapters.get_env", lambda *args: "token")
    client = FakeClient(
        [
            {"date": "2026-01-02", "close": 100.0, "adjusted_close": 99.0, "volume": 1500},
            {"date": "2026-01-03", "close": 102.0, "adjusted_close": 101.0, "volume": 1700},
        ]
    )
    frame = EodhdAdapter(provider("eodhd", "https://example.test", "EODHD_API_TOKEN"), client).load_daily_bars(
        ["SAP.XETRA"], "2026-01-01", "2026-01-04"
    )
    assert frame["close"].tolist() == [99.0, 101.0]
    assert frame["volume"].tolist() == [1500, 1700]
    assert frame["source"].eq("eodhd").all()


def test_finnhub_daily_bars_are_normalised(monkeypatch):
    monkeypatch.setattr("src.data_ingestion.external_adapters.get_env", lambda *args: "token")
    client = FakeClient({"s": "ok", "t": [1767312000, 1767398400], "c": [10.0, 11.0]})
    frame = FinnhubAdapter(provider("finnhub", "https://example.test", "FINNHUB_API_KEY"), client).load_daily_bars(
        ["AAPL"]
    )
    assert len(frame) == 2
    assert frame["return"].iloc[1] == pytest.approx(0.1)


def test_alpha_vantage_daily_bars_are_normalised(monkeypatch):
    values = {
        "ALPHA_VANTAGE_API_KEY": "token",
        "ALPHA_VANTAGE_DAILY_FUNCTION": "TIME_SERIES_DAILY",
        "ALPHA_VANTAGE_OUTPUT_SIZE": "compact",
    }
    monkeypatch.setattr(
        "src.data_ingestion.external_adapters.get_env",
        lambda name, default=None: values.get(name, default),
    )
    client = FakeClient(
        {
            "Meta Data": {"2. Symbol": "AAPL"},
            "Time Series (Daily)": {
                "2026-01-03": {"4. close": "102.0"},
                "2026-01-02": {"4. close": "100.0"},
            },
        }
    )
    frame = AlphaVantageAdapter(
        provider("alpha_vantage", "https://example.test", "ALPHA_VANTAGE_API_KEY"),
        client,
    ).load_daily_bars(["AAPL"], start="2026-01-02", end="2026-01-03")
    assert frame["close"].tolist() == [100.0, 102.0]
    assert frame["source"].eq("alpha_vantage").all()
    assert client.calls[0][1]["function"] == "TIME_SERIES_DAILY"
    assert client.calls[0][1]["outputsize"] == "compact"



def test_tickdb_daily_bars_are_normalised(monkeypatch):
    monkeypatch.setattr("src.data_ingestion.external_adapters.get_env", lambda *args: "token")
    client = FakeClient(
        {
            "code": 0,
            "message": "success",
            "data": {
                "symbol": "700.HK",
                "interval": "1d",
                "klines": [
                    {"time": 1767312000000, "open": "100", "high": "102", "low": "99", "close": "101", "volume": "1000"},
                    {"time": 1767398400000, "open": "101", "high": "103", "low": "100", "close": "102", "volume": "1200"},
                ],
            },
        }
    )
    frame = TickDbAdapter(provider("tickdb", "https://example.test", "TICKDB_API_KEY"), client).load_daily_bars(
        ["700.HK"], start="2026-01-01", end="2026-01-03"
    )
    assert frame["ticker"].eq("700.HK").all()
    assert frame["close"].tolist() == [101.0, 102.0]
    assert frame["volume"].tolist() == [1000.0, 1200.0]
    assert frame["source"].eq("tickdb").all()
    assert client.calls[0][1]["interval"] == "1d"
    assert client.calls[0][2]["X-API-Key"] == "token"
    assert client.calls[0][2]["X-TickDB-Key"] == "token"

def test_itick_medium_article_response_shape_is_normalised(monkeypatch):
    monkeypatch.setattr("src.data_ingestion.external_adapters.get_env", lambda *args: "token")
    client = FakeClient(
        {
            "code": 0,
            "data": [
                {"t": 1767312000000, "o": 100.0, "h": 102.0, "l": 99.0, "c": 101.0, "v": 1000},
                {"t": 1767398400000, "o": 101.0, "h": 103.0, "l": 100.0, "c": 102.0, "v": 1200},
            ],
        }
    )
    frame = ITickAdapter(provider("itick", "https://example.test", "ITICK_API_TOKEN"), client).load_daily_bars(
        ["700"], region="HK"
    )
    assert frame["ticker"].eq("700").all()
    assert frame["close"].tolist() == [101.0, 102.0]
    assert frame["volume"].tolist() == [1000.0, 1200.0]
    assert client.calls[0][1]["region"] == "HK"


def test_frankfurter_v2_rates_are_normalised():
    client = FakeClient(
        [
            {"date": "2026-01-02", "base": "USD", "quote": "EUR", "rate": 0.92, "providers": ["ECB"]},
            {"date": "2026-01-02", "base": "USD", "quote": "GBP", "rate": 0.79, "providers": ["ECB"]},
        ]
    )
    frame = FrankfurterAdapter(provider("frankfurter", "https://example.test"), client).load_fx_rates(
        "USD", ["EUR", "GBP"], "2026-01-01", "2026-01-03"
    )
    assert set(frame["quote_currency"]) == {"EUR", "GBP"}
    assert frame["source"].eq("frankfurter").all()


def test_fred_preserves_realtime_vintage_dates(monkeypatch):
    monkeypatch.setattr("src.data_ingestion.external_adapters.get_env", lambda *args: "token")
    client = FakeClient(
        {
            "observations": [
                {"date": "2025-10-01", "realtime_start": "2026-01-15", "value": "2.5"},
                {"date": "2025-10-01", "realtime_start": "2026-02-15", "value": "2.7"},
            ]
        }
    )
    frame = FredAdapter(provider("fred", "https://example.test", "FRED_API_KEY"), client).load_series("GDP")
    assert len(frame) == 2
    assert frame["vintage_date"].nunique() == 2
    assert client.calls[0][1]["output_type"] == 2


def test_fred_output_type_two_wide_vintages_are_unpivoted(monkeypatch):
    monkeypatch.setattr("src.data_ingestion.external_adapters.get_env", lambda *args: "token")
    client = FakeClient(
        {
            "observations": [
                {
                    "date": "2025-10-01",
                    "GDP_20260115": "2.5",
                    "GDP_20260215": "2.7",
                }
            ]
        }
    )
    frame = FredAdapter(provider("fred", "https://example.test", "FRED_API_KEY"), client).load_series("GDP")
    assert len(frame) == 2
    assert frame["value"].tolist() == [2.5, 2.7]
    assert frame["vintage_date"].tolist() == [
        pd.Timestamp("2026-01-15"),
        pd.Timestamp("2026-02-15"),
    ]


def test_ecb_csv_history_is_normalised():
    csv_text = (
        "KEY,TIME_PERIOD,OBS_VALUE,LAST_UPDATE,UNIT,FREQ\n"
        "EXR.D.USD.EUR.SP00.A,2026-01-02,1.04,2026-01-03,USD,D\n"
    )
    frame = EcbAdapter(provider("ecb", "https://example.test"), FakeClient(text=csv_text)).load_series(
        "EXR", "D.USD.EUR.SP00.A"
    )
    assert frame.loc[0, "value"] == 1.04
    assert frame.loc[0, "source"] == "ecb"


def test_china_data_dataset_is_normalised_with_conservative_availability():
    client = FakeClient(
        {
            "success": True,
            "data": {
                "id": "china-gdp",
                "unit": "100 Million CNY",
                "frequency": "yearly",
                "data": [{"date": "2025", "value": 1401879}],
            },
        }
    )
    frame = ChinaDataAdapter(provider("china_data", "https://example.test"), client).load_dataset("china-gdp")
    assert frame.loc[0, "observation_date"] == pd.Timestamp("2025-01-01")
    assert frame.loc[0, "available_from"] >= frame.loc[0, "observation_date"]


def test_price_combiner_cross_validates_and_keeps_priority_source():
    first = pd.DataFrame(
        {"date": pd.to_datetime(["2026-01-02"]), "ticker": ["A"], "close": [100.0], "return": [0.0], "source": ["eodhd"]}
    )
    second = pd.DataFrame(
        {"date": pd.to_datetime(["2026-01-02"]), "ticker": ["A"], "close": [104.0], "return": [0.0], "source": ["yfinance"]}
    )
    selected = _combine_provider_prices([first, second], ["eodhd", "yfinance"], 0.02)
    assert selected.loc[0, "close"] == 100.0
    assert len(selected.attrs["source_discrepancies"]) == 1


def test_provider_specific_symbols_map_back_to_canonical_ticker():
    registry = load_data_source_registry()
    universe = pd.DataFrame(
        {
            "ticker": ["SAP.DE", "AAPL"],
            "eodhd_ticker": ["SAP.XETRA", "AAPL.US"],
        }
    )
    symbols, reverse_map = _provider_symbols(universe, "eodhd", registry)
    assert symbols == ["AAPL.US", "SAP.XETRA"]
    assert reverse_map["SAP.XETRA"] == "SAP.DE"


def test_http_error_urls_redact_query_credentials():
    safe = redact_url(
        "https://example.test/data?symbol=AAPL&token=secret-token&api_key=secret-key"
    )
    assert "secret-token" not in safe
    assert "secret-key" not in safe
    assert safe.count("%2A%2A%2AREDACTED%2A%2A%2A") == 2
