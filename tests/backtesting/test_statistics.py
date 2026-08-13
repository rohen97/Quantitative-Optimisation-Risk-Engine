import numpy as np
import pandas as pd

from src.backtesting.models import ReplayResult
from src.backtesting.statistics import (
    benchmark_alpha_significance,
    benchmark_relative_summary,
    drawdown_series,
    minimum_track_record_length,
    monte_carlo_simulation,
    moving_block_indices,
    performance_metrics,
    point_in_time_alpha_significance,
    probabilistic_sharpe_ratio,
    strategy_overfitting_diagnostics,
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


def test_drawdown_counts_a_loss_in_the_first_observation() -> None:
    returns = pd.Series([-0.10, 0.05])
    drawdown = drawdown_series(returns)

    assert np.isclose(drawdown.iloc[0], -0.10)
    assert np.isclose(drawdown.iloc[1], -0.055)


def _result(
    key: str,
    values: np.ndarray,
    label: str | None = None,
    evidence_type: str = 'test',
) -> ReplayResult:
    dates = pd.date_range('2018-01-31', periods=len(values), freq='ME')
    monthly = pd.DataFrame(
        {
            'date': dates,
            'net_return': values,
        }
    )
    return ReplayResult(
        key,
        label or key,
        monthly,
        100_000.0,
        'test',
        evidence_type,
        dates[0],
    )


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


def _diagnostic_config() -> dict:
    return {
        'backtest': {'random_seed': 42},
        'resampling': {'samples': 200, 'block_months': 6},
        'statistics': {
            'familywise_alpha': 0.05,
            'lo_autocorrelation_lags': 3,
        },
        'overfitting': {
            'bootstrap_samples': 200,
            'block_months': 6,
            'cscv_slices': 6,
            'minimum_point_in_time_months': 36,
            'random_seed': 7,
        },
    }


def test_benchmark_alpha_uses_newey_west_errors() -> None:
    rng = np.random.default_rng(11)
    benchmark_values = rng.normal(0.004, 0.03, 96)
    strategy_values = 0.006 + 0.75 * benchmark_values + rng.normal(0.0, 0.004, 96)
    strategy = _result(
        'strategy',
        strategy_values,
        evidence_type='research_challenger_replay',
    )
    benchmark = _result('strategy__regional_index', benchmark_values)
    cash = pd.Series(0.0, index=pd.to_datetime(strategy.monthly['date']))

    result = benchmark_alpha_significance(
        [strategy],
        [benchmark],
        cash,
        _diagnostic_config(),
    )

    assert result.loc[0, 'annualised_alpha'] > 0.05
    assert result.loc[0, 'two_sided_p_value'] < 0.05
    assert result.loc[0, 'positive_alpha_significant_5pct']
    assert result.loc[0, 'alpha_claim_status'] == 'RETROSPECTIVE_ONLY'


def test_overfitting_diagnostics_remove_duplicate_trials_and_are_seeded() -> None:
    rng = np.random.default_rng(13)
    first = rng.normal(0.008, 0.03, 72)
    second = rng.normal(0.002, 0.03, 72)
    zero = np.zeros(72)
    strategies = [
        _result('first', first),
        _result('duplicate', first.copy()),
        _result('second', second),
    ]
    benchmarks = [
        _result('first__regional_index', zero),
        _result('duplicate__regional_index', zero),
        _result('second__regional_index', zero),
    ]

    reality_one, summary_one = strategy_overfitting_diagnostics(
        strategies,
        benchmarks,
        _diagnostic_config(),
    )
    reality_two, summary_two = strategy_overfitting_diagnostics(
        strategies,
        benchmarks,
        _diagnostic_config(),
    )

    assert summary_one.loc[0, 'raw_trial_count'] == 3
    assert summary_one.loc[0, 'unique_trial_count'] == 2
    assert summary_one.loc[0, 'probability_of_backtest_overfitting'] >= 0.0
    assert summary_one.loc[0, 'probability_of_backtest_overfitting'] <= 1.0
    duplicate = reality_one.loc[reality_one['strategy'].eq('duplicate')].iloc[0]
    assert duplicate['duplicate_of'] == 'first'
    assert summary_one.equals(summary_two)
    assert reality_one.equals(reality_two)


def test_point_in_time_alpha_requires_history_and_reports_cost_drag() -> None:
    rng = np.random.default_rng(17)
    dates = pd.date_range('2020-01-31', periods=48, freq='ME')
    equal = rng.normal(0.005, 0.025, len(dates))
    cap = rng.normal(0.004, 0.022, len(dates))
    wolf = 0.002 + 0.7 * equal + rng.normal(0.0, 0.006, len(dates))
    monthly = pd.concat(
        [
            pd.DataFrame(
                {
                    'date': dates,
                    'strategy': strategy,
                    'net_return': values,
                    'evidence_mode': 'reconstructed_pit_proxy',
                }
            )
            for strategy, values in (
                ('wolf_cvar', wolf),
                ('equal_weight_eligible', equal),
                ('cap_weight_eligible', cap),
            )
        ],
        ignore_index=True,
    )
    performance = pd.DataFrame(
        {
            'strategy': [
                'wolf_cvar',
                'equal_weight_eligible',
                'cap_weight_eligible',
            ],
            'annualised_cost_drag': [0.025, 0.006, 0.005],
        }
    )

    result = point_in_time_alpha_significance(
        monthly,
        performance,
        _diagnostic_config(),
    )

    assert set(result['benchmark']) == {
        'equal_weight_eligible',
        'cap_weight_eligible',
    }
    assert result['observations'].eq(48).all()
    assert result['incremental_annualised_cost_drag'].gt(0).all()
    assert result['deployable_alpha_status'].eq('NOT_ESTABLISHED').all()
