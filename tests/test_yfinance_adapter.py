import pandas as pd

from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.universe import build_universe
from src.data_ingestion.yfinance_adapter import YFinanceConfig, YFinanceMarketDataAdapter


def test_yfinance_daily_bars_normalize_single_symbol(monkeypatch):
    def fake_download(**kwargs):
        assert kwargs["tickers"] == ["AAPL"]
        return pd.DataFrame(
            {"Close": [100.0, 110.0]},
            index=pd.to_datetime(["2026-01-02", "2026-01-03"]),
        )

    monkeypatch.setattr("src.data_ingestion.yfinance_adapter.yf.download", fake_download)
    bars = YFinanceMarketDataAdapter(YFinanceConfig()).load_daily_bars(["AAPL"], start="2026-01-01", end="2026-01-04")
    assert list(bars.columns) == ["date", "ticker", "close", "return"]
    assert bars["ticker"].tolist() == ["AAPL", "AAPL"]
    assert bars["return"].iloc[0] == 0
    assert round(float(bars["return"].iloc[1]), 4) == 0.1


def test_yfinance_daily_bars_normalize_multi_symbol(monkeypatch):
    columns = pd.MultiIndex.from_product([["Close"], ["AAPL", "MSFT"]])

    def fake_download(**kwargs):
        assert kwargs["tickers"] == ["AAPL", "MSFT"]
        return pd.DataFrame(
            [[100.0, 200.0], [105.0, 210.0]],
            index=pd.to_datetime(["2026-01-02", "2026-01-03"]),
            columns=columns,
        )

    monkeypatch.setattr("src.data_ingestion.yfinance_adapter.yf.download", fake_download)
    bars = YFinanceMarketDataAdapter(YFinanceConfig()).load_daily_bars(["MSFT", "AAPL"], start="2026-01-01", end="2026-01-04")
    assert set(bars["ticker"]) == {"AAPL", "MSFT"}
    assert len(bars) == 4
    assert bars.groupby("ticker")["return"].first().eq(0).all()


def test_price_loader_supports_yfinance_provider(monkeypatch):
    def fake_download(**kwargs):
        return pd.DataFrame(
            {"Close": [100.0, 101.0]},
            index=pd.to_datetime(["2026-01-02", "2026-01-03"]),
        )

    monkeypatch.setattr("src.data_ingestion.yfinance_adapter.yf.download", fake_download)
    monkeypatch.setattr("src.data_ingestion.price_ingestion.get_env", lambda name, default=None: "yfinance" if name == "DATA_PROVIDER" else default)
    prices = load_prices(build_universe(n=1), use_mock=False)
    assert {"date", "ticker", "close", "return"}.issubset(prices.columns)
    assert len(prices) == 2
