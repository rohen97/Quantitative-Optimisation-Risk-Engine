from __future__ import annotations

import hashlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from src.backtesting.config import load_backtest_config
from src.backtesting.engine import build_index_results, replay_all_portfolios
from src.backtesting.market_data import load_market_data
from src.backtesting.portfolio_catalog import build_portfolio_catalog, portfolio_definitions
from src.backtesting.reporting import write_backtest_outputs
from src.backtesting.scenarios import (
    build_monthly_regimes,
    conditional_performance,
    event_definitions,
    macro_event_performance,
)
from src.backtesting.statistics import (
    annual_return_table,
    benchmark_alpha_significance,
    benchmark_relative_summary,
    block_resampling,
    embargo_comparison,
    monte_carlo_simulation,
    performance_summary,
    point_in_time_alpha_significance,
    statistical_significance,
    strategy_overfitting_diagnostics,
)


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _source_hashes(paths: set[Path], root: Path) -> list[dict]:
    rows = []
    for path in sorted(paths):
        if not path.exists():
            continue
        relative = str(path.relative_to(root)).replace(chr(92), '/')
        rows.append({'path': relative, 'sha256': _file_hash(path)})
    return rows


def _git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            cwd=root,
            text=True,
        ).strip()
    except Exception:
        return 'unavailable'


def _load_point_in_time_evidence(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    release = root / 'reports' / 'releases' / '2026-08-07-full-universe' / 'validation'
    summary_path = release / 'portfolio_strategy_comparison.csv'
    summary = pd.read_csv(summary_path) if summary_path.exists() else pd.DataFrame()
    monthly = pd.DataFrame()
    monthly_candidates = (
        release / 'portfolio_monthly_returns.csv',
        root
        / 'reports'
        / 'outputs'
        / 'walk_forward'
        / 'historical_portfolio_returns.parquet',
        release / 'portfolio_performance_by_period.csv',
    )
    for path in monthly_candidates:
        if not path.exists():
            continue
        monthly = (
            pd.read_parquet(path)
            if path.suffix.lower() == '.parquet'
            else pd.read_csv(path)
        )
        if {'date', 'strategy', 'net_return'}.issubset(monthly):
            break
        monthly = pd.DataFrame()
    return summary, monthly


def _bias_and_limitations() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                'category': 'selection look-ahead',
                'severity': 'CRITICAL',
                'applies_to': 'all current portfolio-output replays',
                'status': 'ACKNOWLEDGED',
                'treatment': 'Labelled retrospective holdings replay; excluded from claims of 1997 model selection skill.',
            },
            {
                'category': 'survivorship bias',
                'severity': 'CRITICAL',
                'applies_to': 'current selected securities',
                'status': 'ACKNOWLEDGED',
                'treatment': 'Pre-listing capital stays in T-bills; current holdings are never presented as a historical universe.',
            },
            {
                'category': 'point-in-time model evidence',
                'severity': 'HIGH',
                'applies_to': 'full stock-selection strategy',
                'status': 'SEPARATED',
                'treatment': 'The 25-month reconstructed decision history is reported separately and never spliced into the long replay.',
            },
            {
                'category': 'corporate actions',
                'severity': 'MEDIUM',
                'applies_to': 'holding histories',
                'status': 'MODELED',
                'treatment': 'Yahoo adjusted closes include splits and distributions where provider history supports them.',
            },
            {
                'category': 'currency conversion',
                'severity': 'MEDIUM',
                'applies_to': 'non-USD holdings and indices',
                'status': 'MODELED',
                'treatment': 'Historical FRED FX converts local adjusted closes to USD; ECU bridges pre-euro observations.',
            },
            {
                'category': 'benchmark dividend consistency',
                'severity': 'MEDIUM',
                'applies_to': 'regional price indices',
                'status': 'WARNING',
                'treatment': 'DAX is a performance index; other regional index series may omit dividends. SPY is included as a total-return proxy.',
            },
            {
                'category': 'transaction costs and liquidity',
                'severity': 'MEDIUM',
                'applies_to': 'portfolio outputs and index challenger',
                'status': 'MODELED',
                'treatment': 'Commission, spread, slippage, square-root impact, missing-ADV penalty, and 5% ADV caps are reported.',
            },
            {
                'category': 'annual bank AUM charge',
                'severity': 'MEDIUM',
                'applies_to': 'portfolio outputs and index challenger',
                'status': 'MODELED',
                'treatment': 'A 25 bp charge is deducted once each December from then-current AUM; external benchmarks remain uncharged references.',
            },
            {
                'category': 'conditional regime analysis',
                'severity': 'MEDIUM',
                'applies_to': 'rate, market, and recession tables',
                'status': 'DESCRIPTIVE',
                'treatment': 'Rate and market inputs are lagged one month; NBER recession labels are retrospective and are not presented as tradable signals.',
            },
            {
                'category': 'macro-event windows',
                'severity': 'MEDIUM',
                'applies_to': 'event comparisons and shaded plots',
                'status': 'DESCRIPTIVE',
                'treatment': 'Configured market-response windows overlap monthly returns and do not assert legal conflict dates or isolate causal effects.',
            },
            {
                'category': 'short-sale constraints',
                'severity': 'LOW',
                'applies_to': 'all tested portfolios',
                'status': 'NOT_APPLICABLE',
                'treatment': 'Every tested allocation is long-only; no borrow availability or fee assumption is required.',
            },
            {
                'category': 'multiple testing',
                'severity': 'HIGH',
                'applies_to': 'portfolio comparison',
                'status': 'CONTROLLED',
                'treatment': 'Sidak, Deflated Sharpe, block-bootstrap max-t, duplicate-trial removal, and CSCV PBO are reported.',
            },
            {
                'category': 'deployable alpha',
                'severity': 'CRITICAL',
                'applies_to': 'strategy-selection claims',
                'status': 'NOT_ESTABLISHED',
                'treatment': 'Retrospective alpha is diagnostic only; approval requires native point-in-time outperformance with sufficient history.',
            },
            {
                'category': 'non-stationarity',
                'severity': 'HIGH',
                'applies_to': 'all historical and simulated evidence',
                'status': 'RESIDUAL_RISK',
                'treatment': 'Embargo, subperiod plots, block resampling, fat tails, and EWMA volatility expose but cannot remove structural breaks.',
            },
        ]
    )


def _cost_liquidity_summary(results: list) -> pd.DataFrame:
    rows = []
    for result in results:
        monthly = result.monthly
        unfilled = pd.to_numeric(
            monthly.get('unfilled_target_weight', pd.Series(0.0, index=monthly.index)),
            errors='coerce',
        ).fillna(0.0)
        bank_fees = pd.to_numeric(
            monthly.get('bank_fee_usd', pd.Series(0.0, index=monthly.index)),
            errors='coerce',
        ).fillna(0.0)
        assessments = pd.to_numeric(
            monthly.get(
                'bank_fee_assessment_aum_usd',
                pd.Series(0.0, index=monthly.index),
            ),
            errors='coerce',
        ).fillna(0.0)
        transaction_costs = pd.to_numeric(
            monthly['transaction_cost_usd'],
            errors='coerce',
        ).fillna(0.0)
        rows.append(
            {
                'strategy': result.strategy,
                'total_transaction_cost_usd': float(transaction_costs.sum()),
                'total_bank_fee_usd': float(bank_fees.sum()),
                'total_modeled_cost_usd': float(
                    transaction_costs.sum() + bank_fees.sum()
                ),
                'annual_bank_fee_assessments': int(bank_fees.gt(0.0).sum()),
                'ending_value_before_bank_fee_usd': float(
                    monthly['pre_bank_fee_value_usd'].iloc[-1]
                ),
                'ending_value_after_bank_fee_usd': float(
                    monthly['net_value_usd'].iloc[-1]
                ),
                'ending_value_bank_fee_drag_usd': float(
                    monthly['pre_bank_fee_value_usd'].iloc[-1]
                    - monthly['net_value_usd'].iloc[-1]
                ),
                'effective_bank_fee_bps': (
                    float(bank_fees.sum() / assessments.sum() * 10_000.0)
                    if assessments.sum() > 0
                    else 0.0
                ),
                'average_monthly_turnover': float(monthly['turnover'].mean()),
                'annualised_turnover': float(monthly['turnover'].mean() * 12.0),
                'maximum_adv_participation': float(monthly['maximum_adv_participation'].max()),
                'liquidity_breach_count': int(monthly['liquidity_breaches'].sum()),
                'average_cash_weight': float(monthly['cash_weight'].mean()),
                'average_live_weight': float(monthly['live_weight'].mean()),
                'average_unfilled_target_weight': float(unfilled.mean()),
                'maximum_unfilled_target_weight': float(unfilled.max()),
            }
        )
    return pd.DataFrame(rows)


def _annual_bank_fee_assumption(config: dict) -> pd.DataFrame:
    settings = config['annual_bank_fee']
    reference_aum = float(settings['reference_aum_usd'])
    annual_rate = float(settings['annual_rate'])
    configured_charge = float(settings['reference_annual_charge_usd'])
    calculated_charge = reference_aum * annual_rate
    return pd.DataFrame(
        [
            {
                'label': settings['label'],
                'annual_rate': annual_rate,
                'annual_rate_bps': annual_rate * 10_000.0,
                'charge_month': int(settings['charge_month']),
                'reference_aum_usd': reference_aum,
                'configured_reference_charge_usd': configured_charge,
                'calculated_reference_charge_usd': calculated_charge,
                'reconciliation_difference_usd': (
                    configured_charge - calculated_charge
                ),
                'portfolio_outputs_charged': bool(
                    settings['apply_to_portfolios']
                ),
                'research_challenger_charged': bool(
                    settings['apply_to_research_challenger']
                ),
                'external_benchmarks_charged': bool(
                    settings['apply_to_external_benchmarks']
                ),
            }
        ]
    )


def run_backtest_suite(
    config_path: str | Path | None = None,
    refresh_data: bool | None = None,
) -> dict:
    config = load_backtest_config(config_path)
    if refresh_data is not None:
        config['market_data']['refresh_cache'] = bool(refresh_data)
    root = Path(config['_meta']['repository_root'])
    specs = build_portfolio_catalog(config)
    market_data = load_market_data(specs, config)
    portfolio_results = replay_all_portfolios(specs, market_data, config)
    benchmark_results, index_challenger = build_index_results(specs, market_data, config)
    strategy_results = [*portfolio_results, index_challenger]

    full_starts = [result.full_investment_start for result in portfolio_results]
    common_start = max(value for value in full_starts if value is not None)
    requested_summary = performance_summary(strategy_results, market_data.cash_returns, config)
    common_summary = performance_summary(
        strategy_results,
        market_data.cash_returns,
        config,
        window_start=common_start,
        window_label='common_investable_window',
    )
    individual_summaries = []
    for result in strategy_results:
        if result.full_investment_start is None:
            continue
        individual_summaries.append(
            performance_summary(
                [result],
                market_data.cash_returns,
                config,
                window_start=result.full_investment_start,
                window_label='portfolio_investable_window',
            )
        )
    performance = pd.concat(
        [requested_summary, common_summary, *individual_summaries],
        ignore_index=True,
    )
    benchmark_requested = performance_summary(
        benchmark_results,
        market_data.cash_returns,
        config,
        window_label='requested_1997_window',
    )
    benchmark_common = performance_summary(
        benchmark_results,
        market_data.cash_returns,
        config,
        window_start=common_start,
        window_label='common_investable_window',
    )
    benchmark_performance = pd.concat(
        [benchmark_requested, benchmark_common],
        ignore_index=True,
    )
    standalone_evidence = {
        'common_market_benchmark',
        'standalone_market_benchmark',
        'index_benchmark',
    }
    standalone_benchmarks = [
        result
        for result in benchmark_results
        if result.evidence_type in standalone_evidence
    ]
    standalone_benchmark_performance = benchmark_performance.loc[
        benchmark_performance['evidence_type'].isin(standalone_evidence)
    ].reset_index(drop=True)
    analysis_results = [*strategy_results, *standalone_benchmarks]
    monthly_regimes = build_monthly_regimes(market_data, config)
    rate_level_performance = conditional_performance(
        analysis_results,
        monthly_regimes,
        market_data.cash_returns,
        config,
        'rate_level',
    )
    rate_direction_performance = conditional_performance(
        analysis_results,
        monthly_regimes,
        market_data.cash_returns,
        config,
        'rate_direction',
    )
    market_regime_performance = conditional_performance(
        analysis_results,
        monthly_regimes,
        market_data.cash_returns,
        config,
        'market_regime',
    )
    economic_cycle_performance = conditional_performance(
        analysis_results,
        monthly_regimes,
        market_data.cash_returns,
        config,
        'economic_cycle',
    )
    events = event_definitions(config)
    event_performance = macro_event_performance(
        analysis_results,
        events,
        market_data.cash_returns,
        config,
    )
    requested_relative = benchmark_relative_summary(strategy_results, benchmark_results)
    common_relative = benchmark_relative_summary(
        strategy_results,
        benchmark_results,
        window_start=common_start,
        window_label='common_investable_window',
    )
    relative = pd.concat([requested_relative, common_relative], ignore_index=True)
    alpha_common = benchmark_alpha_significance(
        strategy_results,
        benchmark_results,
        market_data.cash_returns,
        config,
        window_start=common_start,
    )
    alpha_trailing = benchmark_alpha_significance(
        strategy_results,
        benchmark_results,
        market_data.cash_returns,
        config,
        window_start=common_start,
        window_label='last_36_months',
        trailing_months=int(config['backtest']['embargo_months']),
    )
    alpha_significance = pd.concat(
        [alpha_common, alpha_trailing],
        ignore_index=True,
    )
    reality_check, overfitting_summary = strategy_overfitting_diagnostics(
        strategy_results,
        benchmark_results,
        config,
        window_start=common_start,
    )
    significance = statistical_significance(strategy_results, market_data.cash_returns, config)
    ratio_summary = pd.concat(
        [
            common_summary,
            standalone_benchmark_performance.loc[
                standalone_benchmark_performance['window'].eq(
                    'common_investable_window'
                )
            ],
        ],
        ignore_index=True,
    )
    ratio_summary = ratio_summary.merge(
        significance[
            [
                'strategy',
                'probabilistic_sharpe_ratio',
                'minimum_track_record_months',
                'deflated_sharpe_ratio',
                'cluster_adjusted_deflated_sharpe_ratio',
                'sidak_significant',
            ]
        ],
        on='strategy',
        how='left',
    )
    embargo = embargo_comparison(strategy_results, market_data.cash_returns, config)
    annual = annual_return_table(strategy_results)
    resampling_summary, resampling_distribution = block_resampling(
        strategy_results,
        benchmark_results,
        config,
    )
    monte_carlo_summary, monte_carlo_distribution, monte_carlo_diagnostics = monte_carlo_simulation(
        strategy_results,
        config,
    )
    point_in_time_summary, point_in_time_monthly = _load_point_in_time_evidence(root)
    point_in_time_alpha = point_in_time_alpha_significance(
        point_in_time_monthly,
        point_in_time_summary,
        config,
    )
    monthly = pd.concat([result.monthly for result in strategy_results], ignore_index=True)
    benchmark_monthly = pd.concat([result.monthly for result in benchmark_results], ignore_index=True)

    frames = {
        'portfolio_definitions': portfolio_definitions(specs, root),
        'monthly_returns': monthly,
        'benchmark_monthly_returns': benchmark_monthly,
        'performance_summary': performance,
        'benchmark_performance': benchmark_performance,
        'standalone_benchmark_performance': standalone_benchmark_performance,
        'benchmark_relative_summary': relative,
        'benchmark_alpha_significance': alpha_significance,
        'strategy_reality_check': reality_check,
        'strategy_overfitting_summary': overfitting_summary,
        'paper_ratio_summary': ratio_summary,
        'annual_returns': annual,
        'embargo_comparison': embargo,
        'statistical_significance': significance,
        'block_resampling_summary': resampling_summary,
        'monte_carlo_summary': monte_carlo_summary,
        'monte_carlo_diagnostics': monte_carlo_diagnostics,
        'cost_liquidity_summary': _cost_liquidity_summary(strategy_results),
        'annual_bank_fee_assumption': _annual_bank_fee_assumption(config),
        'monthly_regimes': monthly_regimes,
        'interest_rate_level_performance': rate_level_performance,
        'interest_rate_direction_performance': rate_direction_performance,
        'market_regime_performance': market_regime_performance,
        'economic_cycle_performance': economic_cycle_performance,
        'macro_event_definitions': events,
        'macro_event_performance': event_performance,
        'data_coverage': market_data.data_coverage,
        'price_quality_adjustments': market_data.price_adjustments,
        'bias_and_limitations': _bias_and_limitations(),
        'point_in_time_summary': point_in_time_summary,
        'point_in_time_monthly_returns': point_in_time_monthly,
        'point_in_time_alpha_significance': point_in_time_alpha,
    }

    source_paths = {Path(config['_meta']['config_path'])}
    source_paths.update(path for spec in specs for path in spec.source_files)
    paper_path = Path.home() / 'Downloads' / 'The_Three_Types_of_Backtests.pdf'
    paper = (
        {'title': 'The Three Types of Backtests', 'sha256': _file_hash(paper_path)}
        if paper_path.exists()
        else {'title': 'The Three Types of Backtests', 'sha256': 'unavailable'}
    )
    start = pd.Timestamp(config['backtest']['start_date'])
    end = pd.Timestamp(config['backtest']['end_date'])
    pit_months = int(point_in_time_monthly['date'].nunique()) if 'date' in point_in_time_monthly else 0
    manifest = {
        'schema_version': 2,
        'generated_at_utc': datetime.now(UTC).isoformat(),
        'start_date': start.date().isoformat(),
        'end_date': end.date().isoformat(),
        'requested_years': (end - start).days / 365.25,
        'common_investable_start': common_start.date().isoformat(),
        'portfolio_output_count': len(specs),
        'research_challenger_count': 1,
        'standalone_benchmark_count': len(standalone_benchmarks),
        'macro_event_count': len(events),
        'current_portfolio_nav_usd': next(
            spec.initial_capital_usd for spec in specs if spec.key == 'current_portfolio'
        ),
        'fixed_research_capital_usd': float(config['backtest']['default_capital_usd']),
        'point_in_time_months': pit_months,
        'evidence_boundary': 'Long-history outputs are retrospective holdings replays; dated model evidence is separate.',
        'paper': paper,
        'market_data': market_data.source_manifest,
        'resampling': config['resampling'],
        'monte_carlo': config['monte_carlo'],
        'statistics': config['statistics'],
        'overfitting': config.get('overfitting', {}),
        'deployable_alpha_status': (
            str(overfitting_summary.iloc[0]['deployable_alpha_status'])
            if not overfitting_summary.empty
            else 'NOT_EVALUATED'
        ),
        'annual_bank_fee': config['annual_bank_fee'],
        'macro_regimes': config['macro_regimes'],
        'macro_event_method': (
            'Monthly returns are selected when their period overlaps the configured '
            'event window; windows are descriptive and not causal estimates.'
        ),
        'source_artifacts': _source_hashes(source_paths, root),
        'git_commit': _git_commit(root),
        'command': 'python scripts/run_portfolio_backtest_1997.py',
        'uncommitted_simulation_distributions': {
            'block_rows': len(resampling_distribution),
            'monte_carlo_rows': len(monte_carlo_distribution),
            'reason': 'Compact summaries and plots are committed; seeded path-level draws are reproducible and omitted.',
        },
    }
    output_directory = Path(config['backtest']['output_directory'])
    paths = write_backtest_outputs(
        output_directory,
        frames,
        strategy_results,
        config,
        manifest,
    )
    return {
        'config': config,
        'specs': specs,
        'market_data': market_data,
        'strategy_results': strategy_results,
        'benchmark_results': benchmark_results,
        'standalone_benchmark_results': standalone_benchmarks,
        'frames': frames,
        'manifest': manifest,
        'paths': paths,
    }
