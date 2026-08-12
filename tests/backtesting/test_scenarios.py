import numpy as np
import pandas as pd

from src.backtesting.models import MarketDataBundle, ReplayResult
from src.backtesting.scenarios import (
    build_monthly_regimes,
    event_definitions,
    macro_event_performance,
)


def _config() -> dict:
    return {
        'backtest': {'annual_periods': 12},
        'statistics': {'lo_autocorrelation_lags': 2},
        'macro_regimes': {
            'rate_series': 'RATE',
            'recession_series': 'REC',
            'low_rate_upper_pct': 2.0,
            'high_rate_lower_pct': 4.0,
            'rate_direction_lookback_months': 2,
            'rate_direction_threshold_pp': 0.75,
            'market_benchmark_symbol': 'INDEX',
            'market_momentum_lookback_months': 2,
            'market_volatility_lookback_months': 2,
            'market_high_volatility': 1.0,
        },
        'macro_events': [
            {
                'event_id': 'shock',
                'label': 'Test shock',
                'category': 'test',
                'start_date': '2020-02-15',
                'end_date': '2020-02-20',
                'source_url': 'https://example.com',
            }
        ],
    }


def _bundle() -> MarketDataBundle:
    dates = pd.date_range('2020-01-31', periods=6, freq='ME')
    return MarketDataBundle(
        prices_usd=pd.DataFrame(),
        volume_usd=pd.DataFrame(),
        cash_returns=pd.Series(0.0, index=dates),
        benchmark_prices_usd=pd.DataFrame(
            {'INDEX': [100.0, 110.0, 121.0, 125.0, 120.0, 130.0]},
            index=dates,
        ),
        benchmark_metadata=pd.DataFrame(),
        data_coverage=pd.DataFrame(),
        source_manifest={},
        macro_series=pd.DataFrame(
            {
                'RATE': [1.0, 1.5, 3.0, 5.0, 4.5, 3.0],
                'REC': [0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            },
            index=dates,
        ),
    )


def test_regimes_use_information_available_before_return_month() -> None:
    regimes = build_monthly_regimes(_bundle(), _config()).set_index('date')

    assert regimes.loc['2020-02-29', 'rate_pct'] == 1.0
    assert regimes.loc['2020-02-29', 'rate_level'] == 'Low (<2%)'
    assert regimes.loc['2020-04-30', 'rate_direction'] == 'Rising'
    assert regimes.loc['2020-04-30', 'market_regime'] == 'Bull / Calm'
    assert regimes.loc['2020-04-30', 'economic_cycle'] == 'Recession'


def test_event_window_selects_overlapping_month_and_projects_pnl() -> None:
    dates = pd.to_datetime(['2020-01-31', '2020-02-29', '2020-03-31'])
    returns = np.array([0.01, -0.10, 0.05])
    values = 100_000.0 * np.cumprod(1.0 + returns)
    monthly = pd.DataFrame(
        {
            'date': dates,
            'period_start': pd.to_datetime(
                ['2019-12-31', '2020-01-31', '2020-02-29']
            ),
            'net_return': returns,
            'net_value_usd': values,
        }
    )
    result = ReplayResult(
        'strategy',
        'Strategy',
        monthly,
        100_000.0,
        'test',
        'test',
        dates[0],
    )

    summary = macro_event_performance(
        [result],
        event_definitions(_config()),
        _bundle().cash_returns,
        _config(),
    )

    assert summary.loc[0, 'observations'] == 1
    assert np.isclose(summary.loc[0, 'cumulative_return'], -0.10)
    assert np.isclose(summary.loc[0, 'pnl_on_assigned_capital_usd'], -10_000.0)
