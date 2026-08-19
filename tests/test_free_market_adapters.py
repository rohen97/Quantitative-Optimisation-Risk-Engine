from __future__ import annotations

import threading
import time

import pandas as pd

from src.data_ingestion.free_market_adapters import (
    AkshareMarketDataAdapter,
    OpenBBMarketDataAdapter,
    OpenFigiMappingClient,
)
from src.data_ingestion.price_ingestion import _combine_provider_prices, _provider_symbols
from src.data_ingestion.provider_registry import load_data_source_registry


class _Akshare:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def _frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "\u65e5\u671f": ["2026-01-02"],
                "\u5f00\u76d8": [10.0],
                "\u6700\u9ad8": [11.0],
                "\u6700\u4f4e": [9.5],
                "\u6536\u76d8": [10.5],
                "\u6210\u4ea4\u91cf": [12345],
            }
        )

    def stock_hk_hist(self, **kwargs):
        self.calls.append(("hk", kwargs["symbol"]))
        return self._frame()

    def stock_zh_a_hist(self, **kwargs):
        self.calls.append(("a_share", kwargs["symbol"]))
        return self._frame()

    def stock_zh_a_hist_tx(self, **kwargs):
        self.calls.append(("a_share_tencent", kwargs["symbol"]))
        return self._frame()

    def stock_hk_daily(self, **kwargs):
        self.calls.append(("hk_daily", kwargs["symbol"]))
        return self._frame()


def test_akshare_adapter_normalises_china_and_hk_bars():
    module = _Akshare()
    frame = AkshareMarketDataAdapter(module=module, lookback_days=30).load_daily_bars(
        ["700.HK", "000001.SZ", "AAPL"],
        end="2026-01-31",
    )
    assert sorted(module.calls) == sorted(
        [("a_share", "000001"), ("hk", "00700")]
    )
    assert set(frame["ticker"]) == {"000001.SZ", "700.HK"}
    assert frame["volume"].eq(12345).all()
    assert frame["source"].eq("akshare").all()


def test_akshare_adapter_falls_back_to_hk_daily():
    module = _Akshare()

    def fail_primary(**_kwargs):
        raise ConnectionError("primary endpoint unavailable")

    module.stock_hk_hist = fail_primary
    frame = AkshareMarketDataAdapter(module=module).load_daily_bars(
        ["700.HK"], start="2026-01-01", end="2026-01-31"
    )
    assert module.calls == [("hk_daily", "00700")]
    assert len(frame) == 1
    assert frame.loc[0, "ticker"] == "700.HK"


def test_akshare_adapter_can_use_hk_daily_without_slow_primary_probe():
    module = _Akshare()
    frame = AkshareMarketDataAdapter(
        module=module,
        hk_endpoint="daily",
    ).load_daily_bars(["700.HK"], start="2026-01-01", end="2026-01-31")
    assert module.calls == [("hk_daily", "00700")]
    assert len(frame) == 1


def test_akshare_adapter_bounds_parallel_symbol_requests():
    class ConcurrentAkshare(_Akshare):
        def __init__(self):
            super().__init__()
            self.active = 0
            self.maximum_active = 0
            self.lock = threading.Lock()

        def stock_hk_daily(self, **kwargs):
            with self.lock:
                self.active += 1
                self.maximum_active = max(self.maximum_active, self.active)
            try:
                time.sleep(0.02)
                return super().stock_hk_daily(**kwargs)
            finally:
                with self.lock:
                    self.active -= 1

    module = ConcurrentAkshare()
    frame = AkshareMarketDataAdapter(
        module=module,
        hk_endpoint="daily",
        max_workers=2,
    ).load_daily_bars(
        ["1.HK", "2.HK", "3.HK", "4.HK"],
        start="2026-01-01",
        end="2026-01-31",
    )
    assert module.maximum_active == 2
    assert len(frame) == 4


def test_akshare_adapter_warms_hk_daily_runtime_before_parallel_requests():
    class FirstCallUnsafeAkshare(_Akshare):
        def __init__(self):
            super().__init__()
            self.active = 0
            self.initialized = False
            self.lock = threading.Lock()

        def stock_hk_daily(self, **kwargs):
            with self.lock:
                if not self.initialized and self.active:
                    raise RuntimeError("runtime initialized concurrently")
                self.active += 1
            try:
                time.sleep(0.02)
                self.initialized = True
                return super().stock_hk_daily(**kwargs)
            finally:
                with self.lock:
                    self.active -= 1

    module = FirstCallUnsafeAkshare()
    frame = AkshareMarketDataAdapter(
        module=module,
        hk_endpoint="daily",
        max_workers=4,
    ).load_daily_bars(
        ["1.HK", "2.HK", "3.HK", "4.HK"],
        start="2026-01-01",
        end="2026-01-31",
    )
    assert module.initialized
    assert len(frame) == 4


def test_akshare_adapter_retries_transient_a_share_failures():
    class FlakyAkshare(_Akshare):
        def __init__(self):
            super().__init__()
            self.attempts = 0

        def stock_zh_a_hist(self, **kwargs):
            self.attempts += 1
            if self.attempts < 3:
                raise ConnectionError("transient disconnect")
            return super().stock_zh_a_hist(**kwargs)

    module = FlakyAkshare()
    frame = AkshareMarketDataAdapter(
        module=module,
        a_share_endpoint="eastmoney",
        retry_attempts=3,
        retry_backoff_seconds=0,
    ).load_daily_bars(
        ["000001.SZ"],
        start="2026-01-01",
        end="2026-01-31",
    )

    assert module.attempts == 3
    assert len(frame) == 1


def test_akshare_adapter_falls_back_to_tencent_for_a_shares():
    module = _Akshare()

    def fail_primary(**_kwargs):
        raise ConnectionError("primary endpoint unavailable")

    module.stock_zh_a_hist = fail_primary
    frame = AkshareMarketDataAdapter(
        module=module,
        retry_attempts=1,
    ).load_daily_bars(
        ["000001.SZ"],
        start="2026-01-01",
        end="2026-01-31",
    )

    assert module.calls == [("a_share_tencent", "000001")]
    assert len(frame) == 1


class _OpenBBPrices:
    def historical(self, **_kwargs):
        return pd.DataFrame(
            {
                "open": [100.0],
                "high": [102.0],
                "low": [99.0],
                "close": [101.0],
                "volume": [500.0],
            },
            index=pd.DatetimeIndex(["2026-01-02"], name="date"),
        )


class _OpenBBClient:
    class _Equity:
        price = _OpenBBPrices()

    equity = _Equity()


def test_openbb_adapter_normalises_without_importing_optional_package():
    frame = OpenBBMarketDataAdapter(client=_OpenBBClient()).load_daily_bars(["AAPL"])
    assert frame.loc[0, "ticker"] == "AAPL"
    assert frame.loc[0, "close"] == 101.0
    assert frame.loc[0, "source"] == "openbb"


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class _OpenFigiHttp:
    def __init__(self):
        self.jobs = None
        self.headers = None

    def post_json(self, _url, jobs, headers=None):
        self.jobs = jobs
        self.headers = headers
        return _Response(
            [
                {
                    "data": [
                        {
                            "figi": "BBG000B9XRY4",
                            "compositeFIGI": "BBG000B9XRY4",
                            "shareClassFIGI": "BBG001S5N8V8",
                        }
                    ]
                },
                {"error": "No identifier found."},
            ]
        )


def test_openfigi_uses_api_key_header_and_labels_current_snapshot(monkeypatch):
    monkeypatch.setenv("OPENFIGI_API_KEY", "figi-test")
    http = _OpenFigiHttp()
    candidates = pd.DataFrame(
        [
            {"security_id": "AAPL.US", "id_type": "TICKER", "id_value": "AAPL"},
            {"security_id": "MISSING.US", "id_type": "TICKER", "id_value": "MISSING"},
        ]
    )
    result = OpenFigiMappingClient(http, request_pause_seconds=0).map_identifiers(
        candidates,
        retrieved_at=pd.Timestamp("2026-08-19T12:00:00Z"),
        ingestion_run_id="run-openfigi",
    )
    assert http.headers["X-OPENFIGI-APIKEY"] == "figi-test"
    assert result.jobs == 2
    assert result.matched_jobs == 1
    assert result.request_count == 1
    assert set(result.identifiers["identifier_type"]) == {
        "figi",
        "composite_figi",
        "share_class_figi",
    }
    assert result.identifiers["source"].eq("openfigi_current_snapshot").all()
    assert len(result.warnings) == 1


def test_provider_symbols_respect_provider_regions():
    registry = load_data_source_registry()
    universe = pd.DataFrame(
        {
            "ticker": ["AAPL.US", "700.HK"],
            "yfinance_ticker": ["AAPL", "0700.HK"],
            "region": ["US", "Hong Kong"],
        }
    )
    symbols, reverse = _provider_symbols(universe, "akshare", registry)
    assert symbols == ["0700.HK"]
    assert reverse == {"0700.HK": "700.HK"}


def test_price_combiner_keeps_preferred_close_and_fills_secondary_volume():
    preferred = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02"]),
            "ticker": ["A"],
            "close": [100.0],
            "volume": [float("nan")],
            "source": ["yfinance"],
        }
    )
    volume_source = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02"]),
            "ticker": ["A"],
            "close": [104.0],
            "volume": [123.0],
            "source": ["akshare"],
        }
    )
    selected = _combine_provider_prices(
        [preferred, volume_source], ["yfinance", "akshare"], 0.02
    )
    assert selected.loc[0, "close"] == 100.0
    assert selected.loc[0, "volume"] == 123.0
    assert selected.loc[0, "source"] == "yfinance"
