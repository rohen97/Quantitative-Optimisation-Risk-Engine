from __future__ import annotations

import pandas as pd

from src.backtesting.market_data import _cache_key, download_yfinance_history


def test_yfinance_history_repairs_an_incomplete_exact_cache(
    tmp_path,
    monkeypatch,
) -> None:
    start = pd.Timestamp("2024-01-01")
    end = pd.Timestamp("2024-01-31")
    symbols = ["AAA", "BBB"]
    exact_path = tmp_path / f"yfinance_{_cache_key(symbols, start, end)}.parquet"
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02"]),
            "symbol": ["AAA"],
            "adjusted_close": [10.0],
            "volume": [100.0],
        }
    ).to_parquet(exact_path, index=False)
    requested: list[str] = []

    def download(**kwargs):
        requested.extend(kwargs["tickers"])
        columns = pd.MultiIndex.from_product(
            [["Close", "Volume"], kwargs["tickers"]]
        )
        return pd.DataFrame(
            [[20.0, 200.0]],
            index=pd.to_datetime(["2024-01-02"]),
            columns=columns,
        )

    monkeypatch.setattr("src.backtesting.market_data.yf.download", download)
    result, _ = download_yfinance_history(
        symbols,
        start,
        end,
        {"batch_size": 10, "retries": 1},
        tmp_path,
    )

    assert requested == ["BBB"]
    assert set(result["symbol"]) == {"AAA", "BBB"}
