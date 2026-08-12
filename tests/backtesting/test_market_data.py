import numpy as np
import pandas as pd

from src.backtesting.market_data import (
    _normalise_yfinance,
    build_market_data_bundle,
    repair_adjusted_price_outliers,
)
from src.backtesting.models import PortfolioSpec


def test_normalise_yfinance_handles_multi_index_response() -> None:
    dates = pd.to_datetime(['1997-01-02', '1997-01-03'])
    columns = pd.MultiIndex.from_product([['Close', 'Volume'], ['AAA', 'BBB']])
    raw = pd.DataFrame(
        [[10.0, 20.0, 1000.0, 2000.0], [11.0, 19.0, 1100.0, 2100.0]],
        index=dates,
        columns=columns,
    )
    result = _normalise_yfinance(raw, ['AAA', 'BBB'])
    assert set(result['symbol']) == {'AAA', 'BBB'}
    assert len(result) == 4
    assert result.loc[result['symbol'].eq('AAA'), 'adjusted_close'].tolist() == [10.0, 11.0]


def test_build_market_data_bundle_converts_gbp_to_usd() -> None:
    dates = pd.to_datetime(['1997-01-02', '1997-01-03'])
    bars = pd.DataFrame(
        {
            'date': [*dates, *dates, *dates],
            'symbol': ['AAA.L', 'AAA.L', '^GSPC', '^GSPC', 'SPY', 'SPY'],
            'adjusted_close': [100.0, 110.0, 700.0, 707.0, 70.0, 70.7],
            'volume': [1000.0, 1000.0, np.nan, np.nan, 1000.0, 1000.0],
        }
    )
    fred = pd.DataFrame(
        {
            'date': [*dates, *dates],
            'series_id': ['DEXUSUK', 'DEXUSUK', 'DTB3', 'DTB3'],
            'value': [1.5, 1.5, 5.0, 5.0],
        }
    )
    holdings = pd.DataFrame(
        {
            'ticker': ['AAA.L'],
            'yfinance_ticker': ['AAA.L'],
            'weight': [1.0],
            'currency': ['GBP'],
            'region': ['UK'],
        }
    )
    spec = PortfolioSpec('test', 'Test', holdings, 100_000.0, 'test', 'test')
    config = {
        'backtest': {
            'start_date': pd.Timestamp('1997-01-01'),
            'end_date': pd.Timestamp('1997-01-31'),
        },
        'market_data': {
            'risk_free_series': 'DTB3',
            'fx_series': {
                'GBP': {
                    'primary': 'DEXUSUK',
                    'direction': 'usd_per_unit',
                }
            },
        },
        'benchmarks': {
            'common': {'symbol': '^GSPC', 'label': 'S&P 500', 'region': 'US', 'currency': 'USD'},
            'total_return_proxy': {'symbol': 'SPY', 'label': 'SPY', 'region': 'US', 'currency': 'USD'},
            'regions': {
                'US': {'symbol': '^GSPC', 'label': 'S&P 500', 'currency': 'USD'},
            },
        },
    }
    bundle = build_market_data_bundle([spec], config, bars, fred)
    assert bundle.prices_usd.loc[pd.Timestamp('1997-01-02'), 'AAA.L'] == 150.0
    assert bundle.prices_usd.loc[pd.Timestamp('1997-01-03'), 'AAA.L'] == 165.0
    assert bundle.cash_returns.gt(0).any()


def test_price_outlier_repair_records_spikes_and_level_shifts() -> None:
    dates = pd.date_range('2000-01-03', periods=4, freq='D')
    bars = pd.DataFrame(
        {
            'date': [*dates, *dates[:3]],
            'symbol': ['SPIKE'] * 4 + ['SHIFT'] * 3,
            'adjusted_close': [10.0, 40.0, 10.0, 11.0, 10.0, 2.0, 2.2],
            'volume': 1000.0,
        }
    )
    repaired, adjustments = repair_adjusted_price_outliers(bars, 0.50)
    repaired_returns = repaired.groupby('symbol')['adjusted_close'].pct_change(fill_method=None)
    assert repaired_returns.abs().max() <= 0.50
    assert set(adjustments['adjustment_type']) == {
        'isolated_spike_log_interpolation',
        'persistent_level_shift_historical_rescale',
    }
