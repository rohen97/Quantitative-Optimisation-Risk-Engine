from __future__ import annotations

import pandas as pd

from src.backtesting.market_data import download_yfinance_history


def test_yfinance_history_reuses_a_covering_symbol_cache(
    tmp_path,
    monkeypatch,
) -> None:
    prior = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "symbol": ["AAA", "AAA"],
            "adjusted_close": [10.0, 10.5],
            "volume": [100.0, 120.0],
        }
    )
    prior.to_parquet(tmp_path / "yfinance_prior.parquet", index=False)

    def unexpected_download(**_kwargs):
        raise AssertionError("A covered symbol should not be downloaded again.")

    monkeypatch.setattr("src.backtesting.market_data.yf.download", unexpected_download)
    result, cache_path = download_yfinance_history(
        ["AAA"],
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2024-01-31"),
        {"batch_size": 10, "retries": 1},
        tmp_path,
    )

    assert result["symbol"].unique().tolist() == ["AAA"]
    assert cache_path.exists()
    assert (tmp_path / "yfinance_internal").is_dir()


def test_yfinance_history_uses_duckdb_before_network(
    tmp_path,
    monkeypatch,
) -> None:
    local = pd.DataFrame(
        {
            'date': pd.to_datetime(['2024-01-02']),
            'symbol': ['AAA'],
            'adjusted_close': [10.0],
            'volume': [100.0],
        }
    )
    requested: list[str] = []

    monkeypatch.setattr(
        'src.backtesting.market_data._duckdb_price_history',
        lambda symbols, *_args: local.loc[
            local['symbol'].isin(symbols)
        ].copy(),
    )

    def download(**kwargs):
        requested.extend(kwargs['tickers'])
        columns = pd.MultiIndex.from_product(
            [['Close', 'Volume'], kwargs['tickers']]
        )
        return pd.DataFrame(
            [[20.0, 200.0]],
            index=pd.to_datetime(['2024-01-02']),
            columns=columns,
        )

    monkeypatch.setattr('src.backtesting.market_data.yf.download', download)
    result, _ = download_yfinance_history(
        ['AAA', 'BBB'],
        pd.Timestamp('2024-01-01'),
        pd.Timestamp('2024-01-31'),
        {'batch_size': 10, 'retries': 1, 'duckdb_fallback': True},
        tmp_path,
    )

    assert requested == ['BBB']
    assert set(result['symbol']) == {'AAA', 'BBB'}
