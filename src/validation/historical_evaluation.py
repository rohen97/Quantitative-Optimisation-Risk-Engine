from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.validation.alignment import HORIZON_MONTHS, align_forecasts_with_outcomes
from src.validation.binary_calibration import binary_calibration
from src.validation.distribution_calibration import (
    distribution_coverage,
    quantile_crossing_count,
)
from src.validation.forecast_metrics import forecast_accuracy
from src.validation.models import ValidationDataPackage
from src.validation.portfolio_backtesting import calculate_portfolio_performance
from src.validation.regime_validation import performance_by_regime
from src.validation.risk_backtesting import backtest_var
from src.validation.statistics.bootstrap import block_bootstrap_interval
from src.validation.statistics.hypothesis_tests import paired_mean_test
from src.validation.transaction_cost_validation import validate_cost_scenarios


@dataclass(frozen=True)
class HistoricalEvaluation:
    aligned_forecasts: pd.DataFrame
    forecast_accuracy: pd.DataFrame
    forecast_calibration: pd.DataFrame
    distribution_coverage: pd.DataFrame
    binary_calibration: pd.DataFrame
    risk_backtesting: pd.DataFrame
    benchmark_comparison: pd.DataFrame
    period_performance: pd.DataFrame
    regional_performance: pd.DataFrame
    transaction_costs: pd.DataFrame
    regime_performance: pd.DataFrame
    sensitivity: pd.DataFrame
    stability: pd.DataFrame
    significance: pd.DataFrame
    statuses: dict[str, str]
    aligned_observations: int


def _status_frame(
    component: str,
    status: str,
    commentary: str,
    observations: int = 0,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                'component': component,
                'status': status,
                'observation_count': observations,
                'commentary': commentary,
            }
        ]
    )


def _aggregate_status(values: list[str]) -> str:
    evaluated = [value for value in values if value != 'NOT_EVALUATED']
    if not evaluated:
        return 'NOT_EVALUATED'
    if 'FAIL' in evaluated:
        return 'FAIL'
    if 'WARNING' in evaluated:
        return 'WARNING'
    return 'PASS'


def _point_status(metrics: dict, config: dict) -> tuple[str, str]:
    if metrics.get('status') != 'EVALUATED':
        return 'NOT_EVALUATED', 'Minimum aligned observation count was not met.'
    directional = float(metrics['directional_accuracy'])
    rank_ic = float(metrics['rank_ic'])
    normalised_rmse = float(metrics['normalised_rmse'])
    checks = {
        'directional_accuracy': directional
        >= float(config.get('directional_accuracy_threshold', 0.52)),
        'rank_ic': rank_ic >= float(config.get('minimum_rank_ic', 0.02)),
        'normalised_rmse': normalised_rmse
        <= float(config.get('maximum_normalised_rmse', 1.25)),
    }
    if all(checks.values()):
        return 'PASS', 'All configured point-forecast thresholds passed.'
    if rank_ic > 0 and directional >= 0.48:
        failed = ', '.join(name for name, passed in checks.items() if not passed)
        return 'WARNING', f'Positive signal remains, but thresholds missed: {failed}.'
    failed = ', '.join(name for name, passed in checks.items() if not passed)
    return 'FAIL', f'Forecast signal failed material thresholds: {failed}.'


def _distribution_status(metrics: dict, config: dict, crossing: int) -> tuple[str, str]:
    if metrics.get('status') == 'NOT_EVALUATED':
        return 'NOT_EVALUATED', 'Minimum distribution observation count was not met.'
    tolerance = float(config.get('coverage_absolute_tolerance', 0.05))
    errors = {
        'p5': abs(float(metrics['p5_coverage']) - float(config.get('p5_target_coverage', 0.05))),
        'p50': abs(float(metrics['p50_coverage']) - float(config.get('p50_target_coverage', 0.50))),
        'p95': abs(float(metrics['p95_coverage']) - float(config.get('p95_target_coverage', 0.95))),
    }
    if crossing == 0 and all(error <= tolerance for error in errors.values()):
        return 'PASS', 'Quantile ordering and empirical coverage passed.'
    if crossing == 0 and all(error <= 2 * tolerance for error in errors.values()):
        return 'WARNING', 'Quantiles are ordered, with moderate empirical coverage error.'
    return 'FAIL', 'Quantile crossing or material empirical coverage error was observed.'


def _evaluate_forecasts(
    package: ValidationDataPackage,
    forecast_config: dict,
    distribution_config: dict,
    binary_config: dict,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    str,
    str,
]:
    accuracy_rows: list[dict] = []
    calibration_rows: list[dict] = []
    distribution_rows: list[dict] = []
    aligned_frames: list[pd.DataFrame] = []
    for horizon, forecast in package.forecasts.items():
        months = HORIZON_MONTHS.get(str(horizon).upper())
        if months is None:
            continue
        aligned = align_forecasts_with_outcomes(
            forecast,
            package.realised_returns,
            months,
        )
        valid = aligned.dropna(subset=['realised_return', 'expected_total_return']).copy()
        valid['horizon'] = str(horizon).upper()
        aligned_frames.append(valid)
        metrics = forecast_accuracy(
            valid.get('realised_return', pd.Series(dtype=float)),
            valid.get('expected_total_return', pd.Series(dtype=float)),
            int(forecast_config.get('minimum_observations', 30)),
        )
        status, commentary = _point_status(metrics, forecast_config)
        accuracy_rows.append(
            {
                'horizon': str(horizon).upper(),
                **metrics,
                'status': status,
                'commentary': commentary,
            }
        )
        calibration_rows.append(
            {
                'horizon': str(horizon).upper(),
                'status': status,
                'observation_count': len(valid),
                'mean_forecast': pd.to_numeric(
                    valid.get('expected_total_return'),
                    errors='coerce',
                ).mean(),
                'mean_realised': pd.to_numeric(
                    valid.get('realised_return'),
                    errors='coerce',
                ).mean(),
                'forecast_bias': pd.to_numeric(
                    valid.get('expected_total_return'),
                    errors='coerce',
                ).mean()
                - pd.to_numeric(
                    valid.get('realised_return'),
                    errors='coerce',
                ).mean(),
                'commentary': commentary,
            }
        )
        coverage = distribution_coverage(
            valid.get('realised_return', pd.Series(dtype=float)),
            valid.get('p5_return', pd.Series(dtype=float)),
            valid.get('p50_return', pd.Series(dtype=float)),
            valid.get('p95_return', pd.Series(dtype=float)),
            int(distribution_config.get('minimum_pit_observations', 50)),
        )
        crossing = quantile_crossing_count(
            forecast.get('p5_return', pd.Series(dtype=float)),
            forecast.get('p50_return', pd.Series(dtype=float)),
            forecast.get('p95_return', pd.Series(dtype=float)),
        )
        distribution_status, distribution_commentary = _distribution_status(
            coverage,
            distribution_config,
            crossing,
        )
        distribution_rows.append(
            {
                'horizon': str(horizon).upper(),
                **coverage,
                'status': distribution_status,
                'quantile_crossing_count': crossing,
                'commentary': distribution_commentary,
            }
        )
    aligned_all = (
        pd.concat(aligned_frames, ignore_index=True, sort=False)
        if aligned_frames
        else pd.DataFrame()
    )
    accuracy = (
        pd.DataFrame(accuracy_rows)
        if accuracy_rows
        else _status_frame('forecast', 'NOT_EVALUATED', 'No historical forecasts.')
    )
    calibration = (
        pd.DataFrame(calibration_rows)
        if calibration_rows
        else _status_frame('forecast_calibration', 'NOT_EVALUATED', 'No historical forecasts.')
    )
    distribution = (
        pd.DataFrame(distribution_rows)
        if distribution_rows
        else _status_frame('distribution', 'NOT_EVALUATED', 'No historical forecasts.')
    )

    binary = _status_frame(
        'binary_probability_calibration',
        'NOT_EVALUATED',
        'No aligned 12M drawdown events.',
    )
    twelve_month = aligned_all.loc[
        aligned_all.get('horizon', pd.Series(dtype=str)).eq('12M')
    ].copy()
    if (
        not twelve_month.empty
        and 'large_drawdown_probability' in twelve_month
    ):
        event = twelve_month['realised_return'].le(-0.20).astype(int)
        binary_metrics, _ = binary_calibration(
            twelve_month['large_drawdown_probability'],
            event,
            bins=int(binary_config.get('calibration_bins', 10)),
            minimum_observations=int(forecast_config.get('minimum_observations', 30)),
        )
        if binary_metrics.get('status') == 'EVALUATED':
            passed = (
                float(binary_metrics['brier_score'])
                <= float(binary_config.get('maximum_brier_score', 0.25))
                and float(binary_metrics['expected_calibration_error'])
                <= float(
                    binary_config.get('maximum_expected_calibration_error', 0.10)
                )
            )
            binary_status = 'PASS' if passed else 'WARNING'
        else:
            binary_status = 'NOT_EVALUATED'
        binary = pd.DataFrame(
            [
                {
                    'event': 'realised_12m_drawdown_below_20pct',
                    **binary_metrics,
                    'status': binary_status,
                    'event_rate': float(event.mean()) if len(event) else np.nan,
                }
            ]
        )

    regional_rows: list[dict] = []
    if not aligned_all.empty and 'region' in aligned_all:
        for (horizon, region), group in aligned_all.groupby(
            ['horizon', 'region'],
            dropna=False,
        ):
            metrics = forecast_accuracy(
                group['realised_return'],
                group['expected_total_return'],
                int(forecast_config.get('minimum_observations', 30)),
            )
            regional_rows.append(
                {
                    'horizon': horizon,
                    'region': region,
                    **metrics,
                }
            )
    regional = (
        pd.DataFrame(regional_rows)
        if regional_rows
        else _status_frame(
            'regional_performance',
            'NOT_EVALUATED',
            'No aligned regional forecasts.',
        )
    )
    forecast_status = _aggregate_status(accuracy['status'].astype(str).tolist())
    distribution_status = _aggregate_status(
        distribution['status'].astype(str).tolist()
    )
    return (
        aligned_all,
        accuracy,
        calibration,
        distribution,
        binary,
        regional,
        forecast_status,
        distribution_status,
    )


def _evaluate_risk(
    risk_forecasts: pd.DataFrame,
    config: dict,
) -> tuple[pd.DataFrame, str]:
    required = {'realised_return', 'var_95', 'var_99'}
    if risk_forecasts.empty or not required.issubset(risk_forecasts):
        return (
            _status_frame(
                'risk_backtesting',
                'NOT_EVALUATED',
                'Historical portfolio VaR forecasts are unavailable.',
            ),
            'NOT_EVALUATED',
        )
    rows: list[dict] = []
    tolerance = float(config.get('violation_rate_tolerance', 0.02))
    kupiec_threshold = float(config.get('kupiec_pvalue_threshold', 0.05))
    independence_threshold = float(
        config.get('christoffersen_pvalue_threshold', 0.05)
    )
    for confidence, var_column, es_column in (
        (0.95, 'var_95', 'expected_shortfall_95'),
        (0.99, 'var_99', 'expected_shortfall_99'),
    ):
        result = backtest_var(
            risk_forecasts['realised_return'],
            risk_forecasts[var_column],
            confidence,
        )
        expected_rate = 1.0 - confidence
        rate_error = abs(float(result['violation_rate']) - expected_rate)
        passed = (
            rate_error <= tolerance
            and float(result['p_value']) >= kupiec_threshold
            and float(result['christoffersen_p_value']) >= independence_threshold
        )
        warning = (
            rate_error <= 2 * tolerance
            and float(result['p_value']) >= kupiec_threshold / 2
        )
        status = 'PASS' if passed else 'WARNING' if warning else 'FAIL'
        realised = pd.to_numeric(
            risk_forecasts['realised_return'],
            errors='coerce',
        )
        forecast_es = pd.to_numeric(
            risk_forecasts.get(es_column),
            errors='coerce',
        )
        tail = realised.loc[realised.le(realised.quantile(expected_rate))]
        rows.append(
            {
                'confidence_level': confidence,
                **result,
                'expected_violation_rate': expected_rate,
                'violation_rate_error': rate_error,
                'realised_tail_mean': float(tail.mean()),
                'mean_expected_shortfall': float(forecast_es.mean()),
                'expected_shortfall_gap': float(tail.mean() - forecast_es.mean()),
                'status': status,
            }
        )
    frame = pd.DataFrame(rows)
    return frame, _aggregate_status(frame['status'].tolist())


def _evaluate_portfolio(
    package: ValidationDataPackage,
    portfolio_config: dict,
    cost_config: dict,
    regime_config: dict,
    bootstrap_config: dict,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    str,
]:
    returns = package.portfolio_returns.copy()
    required = {
        'date',
        'strategy',
        'gross_return',
        'net_return',
        'transaction_cost',
        'turnover',
    }
    if returns.empty or not required.issubset(returns):
        unavailable = _status_frame(
            'portfolio_performance',
            'NOT_EVALUATED',
            'Historical net strategy returns are unavailable.',
        )
        return (
            unavailable,
            unavailable,
            unavailable,
            unavailable,
            unavailable,
            'NOT_EVALUATED',
        )
    returns['date'] = pd.to_datetime(returns['date'])
    for column in ('gross_return', 'net_return', 'transaction_cost', 'turnover'):
        returns[column] = pd.to_numeric(returns[column], errors='coerce')
    returns = returns.dropna(subset=['gross_return', 'net_return'])
    rows: list[dict] = []
    samples = int(bootstrap_config.get('samples', 1000))
    confidence = float(bootstrap_config.get('confidence_level', 0.95))
    block_size = int(bootstrap_config.get('block_size', 20))
    seed = int(bootstrap_config.get('random_seed', 42))
    for strategy, group in returns.groupby('strategy', sort=False):
        group = group.sort_values('date')
        net = calculate_portfolio_performance(group['net_return'], periods_per_year=12)
        gross = calculate_portfolio_performance(
            group['gross_return'],
            periods_per_year=12,
        )
        lower, upper = block_bootstrap_interval(
            group['net_return'].to_numpy(),
            samples=samples,
            confidence_level=confidence,
            block_size=block_size,
            seed=seed,
        )
        rows.append(
            {
                'strategy': strategy,
                **net.__dict__,
                'gross_annualised_return': gross.annualised_return,
                'annualised_cost_drag': (
                    gross.annualised_return - net.annualised_return
                ),
                'annualised_turnover': float(group['turnover'].mean() * 12),
                'total_transaction_cost': float(group['transaction_cost'].sum()),
                'mean_net_return_ci_lower': lower,
                'mean_net_return_ci_upper': upper,
            }
        )
    benchmark = pd.DataFrame(rows)
    primary = str(package.evidence_manifest.get('primary_strategy', 'wolf_cvar'))
    selected = benchmark.loc[benchmark['strategy'].eq(primary)]
    if selected.empty:
        portfolio_status = 'NOT_EVALUATED'
    else:
        row = selected.iloc[0]
        checks = {
            'minimum_months': int(row['observations'])
            >= int(portfolio_config.get('minimum_backtest_months', 24)),
            'minimum_net_sharpe': float(row['sharpe'])
            >= float(portfolio_config.get('minimum_net_sharpe', 0.25)),
            'maximum_drawdown': float(row['maximum_drawdown'])
            >= float(portfolio_config.get('maximum_drawdown_limit', -0.35)),
            'worst_period': float(row['worst_period'])
            >= float(portfolio_config.get('maximum_single_period_loss', -0.20)),
            'annualised_turnover': float(row['annualised_turnover'])
            <= float(portfolio_config.get('maximum_turnover_annualised', 4.0)),
        }
        if all(checks.values()):
            portfolio_status = 'PASS'
        elif not checks['minimum_months']:
            portfolio_status = 'NOT_EVALUATED'
        elif checks['maximum_drawdown'] and checks['worst_period']:
            portfolio_status = 'WARNING'
        else:
            portfolio_status = 'FAIL'
        benchmark.loc[benchmark['strategy'].eq(primary), 'status'] = portfolio_status
    benchmark['evidence_mode'] = package.evidence_mode
    period = returns.loc[returns['strategy'].eq(primary)].sort_values('date')

    transaction = validate_cost_scenarios(
        returns,
        [float(value) for value in cost_config.get('stress_multiplier', [1.0, 1.5, 2.0])],
    )
    if not transaction.empty:
        transaction['status'] = np.where(
            transaction['net_return'].gt(0),
            'PASS',
            'WARNING',
        )
        transaction['evidence_mode'] = package.evidence_mode

    regime = performance_by_regime(
        period,
        'net_return',
        'regime',
        int(regime_config.get('minimum_observations_per_regime', 20)),
    )

    pivot = returns.pivot_table(
        index='date',
        columns='strategy',
        values='net_return',
        aggfunc='last',
    )
    baseline = 'equal_weight_eligible'
    if primary in pivot and baseline in pivot:
        paired = pivot[[primary, baseline]].dropna()
        test = paired_mean_test(
            paired[primary].to_numpy(),
            paired[baseline].to_numpy(),
        )
        difference = paired[primary] - paired[baseline]
        lower, upper = block_bootstrap_interval(
            difference.to_numpy(),
            samples=samples,
            confidence_level=confidence,
            block_size=block_size,
            seed=seed,
        )
        significance_status = (
            'PASS'
            if float(test['mean_difference']) > 0 and float(test['p_value']) < 0.05
            else 'WARNING'
            if float(test['mean_difference']) > 0
            else 'FAIL'
            if float(test['p_value']) < 0.05
            else 'WARNING'
        )
        significance = pd.DataFrame(
            [
                {
                    'strategy': primary,
                    'baseline': baseline,
                    'observations': len(paired),
                    **test,
                    'difference_ci_lower': lower,
                    'difference_ci_upper': upper,
                    'status': significance_status,
                }
            ]
        )
    else:
        significance = _status_frame(
            'benchmark_significance',
            'NOT_EVALUATED',
            'Primary and equal-weight returns were not aligned.',
        )
    return benchmark, period, transaction, regime, significance, portfolio_status


def _evaluate_stability(
    aligned: pd.DataFrame,
    forecast_config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    if aligned.empty:
        unavailable = _status_frame(
            'stability',
            'NOT_EVALUATED',
            'Aligned forecasts are unavailable.',
        )
        return unavailable, unavailable, 'NOT_EVALUATED'
    sample = aligned.loc[aligned['horizon'].eq('12M')].copy()
    if sample.empty:
        sample = aligned.copy()
    minimum = int(forecast_config.get('minimum_observations', 30))
    full = forecast_accuracy(
        sample['realised_return'],
        sample['expected_total_return'],
        minimum,
    )
    rows = [
        {
            'excluded_dimension': 'none',
            'excluded_group': 'none',
            **full,
        }
    ]
    for dimension in ('region',):
        if dimension not in sample:
            continue
        for value in sample[dimension].dropna().unique():
            remaining = sample.loc[sample[dimension].ne(value)]
            metrics = forecast_accuracy(
                remaining['realised_return'],
                remaining['expected_total_return'],
                minimum,
            )
            rows.append(
                {
                    'excluded_dimension': dimension,
                    'excluded_group': value,
                    **metrics,
                }
            )
    years = pd.to_datetime(sample['as_of_date']).dt.year
    for year in sorted(years.dropna().unique()):
        remaining = sample.loc[years.ne(year)]
        metrics = forecast_accuracy(
            remaining['realised_return'],
            remaining['expected_total_return'],
            minimum,
        )
        rows.append(
            {
                'excluded_dimension': 'forecast_year',
                'excluded_group': int(year),
                **metrics,
            }
        )
    stability = pd.DataFrame(rows)
    stability['rank_ic_change'] = (
        stability['rank_ic'] - float(full.get('rank_ic', np.nan))
    )
    evaluated = stability.loc[stability['status'].eq('EVALUATED')]
    full_rank = float(full.get('rank_ic', np.nan))
    if evaluated.empty or not np.isfinite(full_rank):
        stability_status = 'NOT_EVALUATED'
    elif full_rank <= 0 or float(evaluated['rank_ic'].min()) <= 0:
        stability_status = 'FAIL'
    elif float(evaluated['rank_ic_change'].abs().max()) <= 0.10:
        stability_status = 'PASS'
    else:
        stability_status = 'WARNING'
    stability['validation_status'] = stability_status

    sensitivity_rows: list[dict] = []
    baseline_rmse = float(full.get('normalised_rmse', np.nan))
    for scale in (0.80, 0.90, 1.10, 1.20):
        metrics = forecast_accuracy(
            sample['realised_return'],
            sample['expected_total_return'] * scale,
            minimum,
        )
        sensitivity_rows.append(
            {
                'parameter': 'expected_return_scale',
                'relative_change': scale - 1.0,
                'scale': scale,
                **metrics,
                'normalised_rmse_change': float(
                    metrics.get('normalised_rmse', np.nan)
                )
                - baseline_rmse,
            }
        )
    sensitivity = pd.DataFrame(sensitivity_rows)
    evaluated_sensitivity = sensitivity.loc[sensitivity['status'].eq('EVALUATED')]
    if evaluated_sensitivity.empty:
        sensitivity_status = 'NOT_EVALUATED'
    elif (
        evaluated_sensitivity['normalised_rmse_change'].abs().max() <= 0.25
        and evaluated_sensitivity['directional_accuracy'].min() >= 0.48
    ):
        sensitivity_status = 'PASS'
    else:
        sensitivity_status = 'WARNING'
    sensitivity['validation_status'] = sensitivity_status
    combined = _aggregate_status([stability_status, sensitivity_status])
    return sensitivity, stability, combined


def evaluate_historical_evidence(
    package: ValidationDataPackage,
    validation_config: dict,
) -> HistoricalEvaluation:
    (
        aligned,
        accuracy,
        calibration,
        distribution,
        binary,
        regional,
        forecast_status,
        distribution_status,
    ) = _evaluate_forecasts(
        package,
        validation_config.get('forecast', {}),
        validation_config.get('distributions', {}),
        validation_config.get('binary_probabilities', {}),
    )
    risk, risk_status = _evaluate_risk(
        package.risk_forecasts,
        validation_config.get('risk', {}),
    )
    (
        benchmark,
        period,
        transaction,
        regime,
        significance,
        portfolio_status,
    ) = _evaluate_portfolio(
        package,
        validation_config.get('portfolio', {}),
        validation_config.get('costs', {}),
        validation_config.get('regime', {}),
        validation_config.get('bootstrap', {}),
    )
    sensitivity, stability, stability_status = _evaluate_stability(
        aligned,
        validation_config.get('forecast', {}),
    )
    transaction_status = (
        _aggregate_status(transaction['status'].astype(str).tolist())
        if 'status' in transaction
        else 'NOT_EVALUATED'
    )
    if portfolio_status == 'FAIL':
        portfolio_component_status = 'FAIL'
    elif portfolio_status == 'NOT_EVALUATED':
        portfolio_component_status = 'NOT_EVALUATED'
    elif portfolio_status == 'PASS' and transaction_status == 'PASS':
        portfolio_component_status = 'PASS'
    else:
        portfolio_component_status = 'WARNING'
    return HistoricalEvaluation(
        aligned_forecasts=aligned,
        forecast_accuracy=accuracy,
        forecast_calibration=calibration,
        distribution_coverage=distribution,
        binary_calibration=binary,
        risk_backtesting=risk,
        benchmark_comparison=benchmark,
        period_performance=period,
        regional_performance=regional,
        transaction_costs=transaction,
        regime_performance=regime,
        sensitivity=sensitivity,
        stability=stability,
        significance=significance,
        statuses={
            'forecast_performance': forecast_status,
            'distribution_calibration': distribution_status,
            'risk_backtesting': risk_status,
            'portfolio_net_of_costs': portfolio_component_status,
            'stability_sensitivity': stability_status,
        },
        aligned_observations=len(aligned),
    )
