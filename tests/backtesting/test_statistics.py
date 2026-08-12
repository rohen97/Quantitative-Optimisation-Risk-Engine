import numpy as np
import pandas as pd

from src.backtesting.models import ReplayResult
from src.backtesting.statistics import (
    benchmark_relative_summary,
    minimum_track_record_length,
    monte_carlo_simulation,
    moving_block_indices,
    performance_metrics,
    probabilistic_sharpe_ratio,
)


def test_probabilistic_sharpe_and_minimum_track_record() -> None:
    probability = probabilistic_sharpe_ratio(0.20, 0.0, 120, 0.0, 3.0)
    minimum = minimum_track_record_length(0.20, 0.0, 0.0, 3.0)
    assert probability > 0.95
    assert 1 < minimum < 120


def test_moving_block_indices_are_reproducible_and_bounded() -> None:
    first = moving_block_indices(25, 20, 6, 42)
    second = moving_block_indices(25, 20, 6, 42)
    assert first.shape == (20, 25)
    assert np.array_equal(first, second)
    assert first.min() >= 0
    assert first.max() < 25


def test_performance_metrics_projects_assigned_capital() -> None:
    dates = pd.date_range('2020-01-31', periods=24, freq='ME')
    returns = pd.Series(0.01, index=dates)
    metrics = performance_metrics(returns, 100_000.0)
    assert metrics['cagr'] > 0.12
    assert metrics['ending_value_usd'] > 126_000.0
    assert metrics['maximum_drawdown'] == 0.0


def _result(key: str, values: np.ndarray, label: str | None = None) -> ReplayResult:
    dates = pd.date_range('2018-01-31', periods=len(values), freq='ME')
    monthly = pd.DataFrame(
        {
            'date': dates,
            'net_return': values,
        }
    )
    return ReplayResult(key, label or key, monthly, 100_000.0, 'test', 'test', dates[0])


def test_monte_carlo_is_seeded_and_finite() -> None:
    rng = np.random.default_rng(7)
    first = rng.normal(0.008, 0.04, 72)
    second = 0.6 * first + rng.normal(0.003, 0.025, 72)
    config = {
        'backtest': {'random_seed': 42},
        'monte_carlo': {
            'paths': 100,
            'horizon_months': 24,
            'ewma_lambda': 0.94,
            'minimum_degrees_of_freedom': 5.0,
            'maximum_degrees_of_freedom': 30.0,
        },
    }
    summary_one, _, diagnostics = monte_carlo_simulation(
        [_result('first', first), _result('second', second)],
        config,
        selected_strategies={'first'},
    )
    summary_two, _, _ = monte_carlo_simulation(
        [_result('first', first), _result('second', second)],
        config,
        selected_strategies={'first'},
    )
    assert len(summary_one) == 2
    assert np.isfinite(summary_one['cagr_median']).all()
    assert summary_one['cagr_median'].equals(summary_two['cagr_median'])
    assert diagnostics['ar1_coefficient'].between(-0.30, 0.30).all()


def test_benchmark_relative_summary_applies_window_and_labels() -> None:
    strategy = _result('strategy', np.full(6, 0.01))
    benchmark = _result('strategy__regional_index', np.zeros(6), 'Regional Index')
    window_start = pd.Timestamp(strategy.monthly.loc[3, 'date'])

    summary = benchmark_relative_summary(
        [strategy],
        [benchmark],
        window_start=window_start,
        window_label='common_investable_window',
    )

    assert summary.loc[0, 'window'] == 'common_investable_window'
    assert summary.loc[0, 'strategy_label'] == strategy.label
    assert summary.loc[0, 'benchmark_label'] == 'Regional Index'
    assert summary.loc[0, 'observations'] == 3
