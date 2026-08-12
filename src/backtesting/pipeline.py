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
from src.backtesting.statistics import (
    annual_return_table,
    benchmark_relative_summary,
    block_resampling,
    embargo_comparison,
    monte_carlo_simulation,
    performance_summary,
    statistical_significance,
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
    monthly_path = release / 'portfolio_performance_by_period.csv'
    summary = pd.read_csv(summary_path) if summary_path.exists() else pd.DataFrame()
    monthly = pd.read_csv(monthly_path) if monthly_path.exists() else pd.DataFrame()
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
                'treatment': 'Sidak FWER and Deflated Sharpe Ratios use both actual and correlation-clustered trial counts.',
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
        rows.append(
            {
                'strategy': result.strategy,
                'total_transaction_cost_usd': float(monthly['transaction_cost_usd'].sum()),
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
    requested_relative = benchmark_relative_summary(strategy_results, benchmark_results)
    common_relative = benchmark_relative_summary(
        strategy_results,
        benchmark_results,
        window_start=common_start,
        window_label='common_investable_window',
    )
    relative = pd.concat([requested_relative, common_relative], ignore_index=True)
    significance = statistical_significance(strategy_results, market_data.cash_returns, config)
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
    monthly = pd.concat([result.monthly for result in strategy_results], ignore_index=True)
    benchmark_monthly = pd.concat([result.monthly for result in benchmark_results], ignore_index=True)

    frames = {
        'portfolio_definitions': portfolio_definitions(specs, root),
        'monthly_returns': monthly,
        'benchmark_monthly_returns': benchmark_monthly,
        'performance_summary': performance,
        'benchmark_performance': benchmark_performance,
        'benchmark_relative_summary': relative,
        'annual_returns': annual,
        'embargo_comparison': embargo,
        'statistical_significance': significance,
        'block_resampling_summary': resampling_summary,
        'monte_carlo_summary': monte_carlo_summary,
        'monte_carlo_diagnostics': monte_carlo_diagnostics,
        'cost_liquidity_summary': _cost_liquidity_summary(strategy_results),
        'data_coverage': market_data.data_coverage,
        'price_quality_adjustments': market_data.price_adjustments,
        'bias_and_limitations': _bias_and_limitations(),
        'point_in_time_summary': point_in_time_summary,
        'point_in_time_monthly_returns': point_in_time_monthly,
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
        'schema_version': 1,
        'generated_at_utc': datetime.now(UTC).isoformat(),
        'start_date': start.date().isoformat(),
        'end_date': end.date().isoformat(),
        'requested_years': (end - start).days / 365.25,
        'common_investable_start': common_start.date().isoformat(),
        'portfolio_output_count': len(specs),
        'research_challenger_count': 1,
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
        'frames': frames,
        'manifest': manifest,
        'paths': paths,
    }
