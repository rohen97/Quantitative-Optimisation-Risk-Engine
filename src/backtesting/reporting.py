from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from jinja2 import Template

from src.backtesting.models import ReplayResult
from src.backtesting.runtime import configure_font_environment
from src.backtesting.statistics import drawdown_series


PALETTE = [
    '#145A64',
    '#C44E52',
    '#D69E2E',
    '#2F855A',
    '#5B4B8A',
    '#2B6CB0',
    '#B35C1E',
    '#6B7280',
    '#0F766E',
    '#9F3A5B',
    '#4A5568',
    '#718C3A',
    '#7C3D12',
    '#1D4ED8',
]


def _style() -> None:
    plt.rcParams.update(
        {
            'figure.facecolor': 'white',
            'axes.facecolor': '#F8FAFC',
            'axes.edgecolor': '#CBD5E1',
            'axes.grid': True,
            'grid.color': '#E2E8F0',
            'grid.linewidth': 0.7,
            'font.family': 'DejaVu Sans',
            'font.size': 9,
            'axes.titleweight': 'bold',
            'axes.titlesize': 13,
            'axes.labelsize': 9,
            'legend.frameon': False,
            'savefig.dpi': 170,
            'savefig.bbox': 'tight',
        }
    )


def _save(fig: plt.Figure, path: Path) -> None:
    fig.savefig(path, facecolor='white')
    plt.close(fig)


def plot_wealth_paths(
    monthly: pd.DataFrame,
    labels: dict[str, str],
    path: Path,
) -> None:
    _style()
    fig, axis = plt.subplots(figsize=(13, 7))
    for index, (strategy, group) in enumerate(monthly.groupby('strategy', sort=False)):
        ordered = group.sort_values('date')
        indexed = ordered['net_value_usd'] / float(ordered['initial_capital_usd'].iloc[0]) * 100.0
        axis.plot(
            pd.to_datetime(ordered['date']),
            indexed,
            label=labels.get(strategy, strategy),
            color=PALETTE[index % len(PALETTE)],
            linewidth=1.45,
            alpha=0.92,
        )
    axis.set_yscale('log')
    axis.set_title('Growth of $100 Equivalent, Net of Modeled Costs')
    axis.set_ylabel('Indexed wealth, log scale')
    axis.set_xlabel('')
    axis.legend(loc='upper left', bbox_to_anchor=(1.01, 1.0), ncol=1, fontsize=8)
    _save(fig, path)


def plot_benchmark_comparison(
    monthly: pd.DataFrame,
    benchmark_monthly: pd.DataFrame,
    labels: dict[str, str],
    path: Path,
) -> None:
    selected = [
        'current_portfolio',
        'final_portfolio',
        'clean_sheet',
        'llm_benchmark',
        'trend_risk_controlled_indices',
        'common_index',
        'total_return_proxy',
        'equal_weight_regional_indices',
        'final_portfolio__regional_index',
    ]
    combined = pd.concat([monthly, benchmark_monthly], ignore_index=True)
    _style()
    fig, axis = plt.subplots(figsize=(13, 7))
    for index, strategy in enumerate(selected):
        group = combined.loc[combined['strategy'].eq(strategy)].sort_values('date')
        if group.empty:
            continue
        indexed = group['net_value_usd'] / float(group['initial_capital_usd'].iloc[0]) * 100.0
        is_benchmark = strategy in {
            'common_index',
            'total_return_proxy',
            'equal_weight_regional_indices',
            'final_portfolio__regional_index',
        }
        axis.plot(
            pd.to_datetime(group['date']),
            indexed,
            label=labels.get(strategy, strategy),
            color=PALETTE[index % len(PALETTE)],
            linewidth=2.0 if is_benchmark else 1.35,
            linestyle='--' if is_benchmark else '-',
            alpha=0.95,
        )
    axis.set_yscale('log')
    axis.set_title('Selected Portfolios Against Broad and Regional Index Benchmarks')
    axis.set_ylabel('Indexed wealth, log scale')
    axis.set_xlabel('')
    axis.legend(loc='upper left', bbox_to_anchor=(1.01, 1.0), fontsize=8)
    _save(fig, path)


def plot_ending_pnl(summary: pd.DataFrame, path: Path) -> None:
    _style()
    data = summary.loc[summary['window'].eq('requested_1997_window')].sort_values('pnl_usd')
    colors = np.where(data['pnl_usd'].ge(0), '#147D6F', '#C44E52')
    fig, axis = plt.subplots(figsize=(11, 7))
    axis.barh(data['strategy_label'], data['pnl_usd'], color=colors)
    axis.axvline(0.0, color='#334155', linewidth=0.8)
    axis.set_title('Historical PnL at the Assigned Starting Capital')
    axis.set_xlabel('Net PnL, USD')
    axis.grid(axis='y', visible=False)
    axis.xaxis.set_major_formatter(lambda value, _: f'${value:,.0f}')
    _save(fig, path)


def plot_risk_return(summary: pd.DataFrame, path: Path) -> None:
    _style()
    data = summary.loc[summary['window'].eq('common_investable_window')].copy()
    if data.empty:
        data = summary.loc[summary['window'].eq('requested_1997_window')].copy()
    fig, axis = plt.subplots(figsize=(11, 7))
    for index, row in data.reset_index(drop=True).iterrows():
        size = 70.0 + 300.0 * abs(float(row['maximum_drawdown']))
        axis.scatter(
            row['annualised_volatility'],
            row['cagr'],
            s=size,
            label=row['strategy_label'],
            color=PALETTE[index % len(PALETTE)],
            edgecolor='white',
            linewidth=0.8,
            zorder=3,
        )
    axis.axhline(0.0, color='#64748B', linewidth=0.8)
    axis.set_title('Return, Risk and Drawdown on the Common Investable Window')
    axis.set_xlabel('Annualised volatility')
    axis.set_ylabel('CAGR')
    axis.xaxis.set_major_formatter(lambda value, _: f'{value:.0%}')
    axis.yaxis.set_major_formatter(lambda value, _: f'{value:.0%}')
    axis.legend(loc='upper left', bbox_to_anchor=(1.01, 1.0), fontsize=8)
    _save(fig, path)


def plot_drawdowns(results: list[ReplayResult], path: Path) -> None:
    _style()
    selected = {
        'current_portfolio',
        'final_portfolio',
        'clean_sheet',
        'llm_benchmark',
        'trend_risk_controlled_indices',
    }
    fig, axis = plt.subplots(figsize=(12, 6))
    plotted = 0
    for result in results:
        if result.strategy not in selected:
            continue
        returns = result.monthly.set_index('date')['net_return'].sort_index()
        axis.plot(
            returns.index,
            drawdown_series(returns),
            label=result.label,
            color=PALETTE[plotted % len(PALETTE)],
            linewidth=1.5,
        )
        plotted += 1
    axis.set_title('Drawdown Comparison')
    axis.set_ylabel('Drawdown')
    axis.yaxis.set_major_formatter(lambda value, _: f'{value:.0%}')
    axis.legend(loc='lower left', ncol=2)
    _save(fig, path)


def plot_annual_heatmap(
    annual_returns: pd.DataFrame,
    labels: dict[str, str],
    path: Path,
) -> None:
    _style()
    pivot = annual_returns.pivot(index='strategy', columns='year', values='return')
    pivot = pivot.reindex([key for key in labels if key in pivot.index])
    fig_height = max(5.0, 0.42 * len(pivot) + 2.0)
    fig, axis = plt.subplots(figsize=(14, fig_height))
    image = axis.imshow(
        pivot.to_numpy(),
        aspect='auto',
        cmap='RdYlGn',
        vmin=-0.35,
        vmax=0.35,
    )
    years = list(pivot.columns)
    ticks = list(range(0, len(years), 2))
    axis.set_xticks(ticks, [str(years[index]) for index in ticks], rotation=45, ha='right')
    axis.set_yticks(range(len(pivot)), [labels.get(key, key) for key in pivot.index])
    axis.set_title('Calendar-Year Net Returns')
    axis.grid(False)
    colorbar = fig.colorbar(image, ax=axis, fraction=0.025, pad=0.02)
    colorbar.ax.yaxis.set_major_formatter(lambda value, _: f'{value:.0%}')
    _save(fig, path)


def plot_interval_summary(
    data: pd.DataFrame,
    labels: dict[str, str],
    path: Path,
    title: str,
) -> None:
    _style()
    ordered = data.sort_values('cagr_median').reset_index(drop=True)
    y = np.arange(len(ordered))
    lower = ordered['cagr_median'] - ordered['cagr_p05']
    upper = ordered['cagr_p95'] - ordered['cagr_median']
    fig, axis = plt.subplots(figsize=(11, max(6, len(ordered) * 0.42 + 2)))
    axis.errorbar(
        ordered['cagr_median'],
        y,
        xerr=np.vstack([lower, upper]),
        fmt='o',
        color='#145A64',
        ecolor='#94A3B8',
        capsize=3,
        markersize=5,
    )
    axis.axvline(0.0, color='#C44E52', linewidth=0.9)
    axis.set_yticks(y, [labels.get(key, key) for key in ordered['strategy']])
    axis.set_title(title)
    axis.set_xlabel('CAGR: 5th percentile, median, 95th percentile')
    axis.xaxis.set_major_formatter(lambda value, _: f'{value:.0%}')
    axis.grid(axis='y', visible=False)
    _save(fig, path)


def plot_embargo(embargo: pd.DataFrame, labels: dict[str, str], path: Path) -> None:
    _style()
    pivot = embargo.pivot_table(index='strategy', columns='period', values='sharpe')
    pivot = pivot.sort_values('untouched_embargo')
    y = np.arange(len(pivot))
    fig, axis = plt.subplots(figsize=(11, max(6, len(pivot) * 0.43 + 2)))
    axis.barh(y - 0.18, pivot['development'], height=0.34, label='Development', color='#5B7083')
    axis.barh(y + 0.18, pivot['untouched_embargo'], height=0.34, label='Untouched 36 months', color='#D69E2E')
    axis.axvline(0.0, color='#334155', linewidth=0.8)
    axis.set_yticks(y, [labels.get(key, key) for key in pivot.index])
    axis.set_title('Development vs Untouched Embargo Sharpe')
    axis.set_xlabel('Annualised Sharpe ratio')
    axis.legend(loc='lower right')
    axis.grid(axis='y', visible=False)
    _save(fig, path)


def plot_investable_starts(summary: pd.DataFrame, path: Path) -> None:
    _style()
    data = summary.loc[summary['window'].eq('requested_1997_window')].copy()
    data['full_investment_start'] = pd.to_datetime(data['full_investment_start'])
    data = data.sort_values('full_investment_start', na_position='last')
    y = np.arange(len(data))
    start = pd.Timestamp('1997-01-01')
    end = pd.to_datetime(data['end_date']).max()
    fig, axis = plt.subplots(figsize=(12, max(6, len(data) * 0.43 + 2)))
    for index, row in data.reset_index(drop=True).iterrows():
        available = row['full_investment_start']
        if pd.isna(available):
            continue
        axis.hlines(index, start, available, color='#CBD5E1', linewidth=5)
        axis.hlines(index, available, end, color='#147D6F', linewidth=5)
        axis.scatter(available, index, color='#D69E2E', s=28, zorder=3)
    axis.set_yticks(y, data['strategy_label'])
    axis.set_xlim(start, end)
    axis.set_title('When at Least 80% of Each Intended Asset Allocation Was Tradable')
    axis.set_xlabel('Grey: pre-listing allocation held in T-bills; green: investable')
    axis.grid(axis='y', visible=False)
    _save(fig, path)


def plot_causal_graph(path: Path) -> None:
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

    _style()
    fig, axis = plt.subplots(figsize=(13, 6))
    axis.set_xlim(0, 13)
    axis.set_ylim(0, 6)
    axis.axis('off')
    nodes = {
        'Reported quality\nand cash flow': (0.6, 4.0, '#DCEFEA'),
        'Dividend safety\nand valuation': (0.6, 1.2, '#F9E8C7'),
        'Regime and\ndownside risk': (4.2, 1.2, '#E6E1F0'),
        'Resilient future\ncash distributions': (4.2, 4.0, '#D9E8F5'),
        'Constrained target\nportfolio': (7.9, 4.0, '#DCEFEA'),
        'Trading costs, FX\nand liquidity': (7.9, 1.2, '#F4D9D9'),
        'Net USD return\nand drawdown': (11.0, 2.6, '#E2E8F0'),
    }
    for label, (x, y, color) in nodes.items():
        box = FancyBboxPatch(
            (x, y),
            1.8,
            0.85,
            boxstyle='round,pad=0.08,rounding_size=0.04',
            facecolor=color,
            edgecolor='#475569',
            linewidth=1.0,
        )
        axis.add_patch(box)
        axis.text(x + 0.9, y + 0.425, label, ha='center', va='center', fontsize=9)
    arrows = [
        ((2.4, 4.42), (4.2, 4.42)),
        ((2.4, 1.62), (4.2, 4.05)),
        ((6.0, 4.42), (7.9, 4.42)),
        ((6.0, 1.62), (8.1, 4.02)),
        ((9.7, 4.42), (11.0, 3.35)),
        ((9.7, 1.62), (11.0, 2.75)),
    ]
    for source, target in arrows:
        axis.add_patch(
            FancyArrowPatch(
                source,
                target,
                arrowstyle='-|>',
                mutation_scale=12,
                linewidth=1.1,
                color='#64748B',
            )
        )
    axis.set_title('Causal Theory Tested by the Model and Degraded by Execution Frictions', pad=14)
    _save(fig, path)


def _format_value(column: str, value: object) -> str:
    if pd.isna(value):
        return ''
    name = column.lower()
    if 'usd' in name:
        return f'${float(value):,.0f}'
    if any(token in name for token in ('probabilistic', 'deflated', 'probability')):
        return f'{float(value):.2%}'
    percentage_ratios = {'positive_month_ratio', 'outperformance_month_ratio'}
    if name in percentage_ratios or any(
        token in name
        for token in ('return', 'cagr', 'volatility', 'drawdown', 'alpha', 'turnover', 'weight', 'participation')
    ):
        return f'{float(value):.2%}'
    if any(token in name for token in ('sharpe', 'sortino', 'calmar', 'beta', 'information_ratio', 'capture')):
        return f'{float(value):.2f}'
    if isinstance(value, (float, np.floating)):
        return f'{float(value):.3f}'
    return str(value)


def _html_table(data: pd.DataFrame, columns: list[str], rename: dict[str, str] | None = None) -> str:
    available = [column for column in columns if column in data]
    if not available or data.empty:
        return '<p>No evaluated observations.</p>'
    frame = data[available].copy()
    for column in frame:
        frame[column] = frame[column].map(lambda value: _format_value(column, value))
    if rename:
        frame = frame.rename(columns=rename)
    return frame.to_html(index=False, border=0, classes='data-table', escape=True)


def _markdown_performance_table(summary: pd.DataFrame) -> str:
    columns = ['strategy_label', 'initial_capital_usd', 'cagr', 'sharpe', 'maximum_drawdown', 'ending_value_usd', 'pnl_usd']
    header = '| Portfolio | Start | CAGR | Sharpe | Max drawdown | Ending value | PnL |'
    separator = '|---|---:|---:|---:|---:|---:|---:|'
    rows = [header, separator]
    for row in summary[columns].itertuples(index=False):
        rows.append(
            f'| {row.strategy_label} | ${row.initial_capital_usd:,.0f} | {row.cagr:.2%} | '
            f'{row.sharpe:.2f} | {row.maximum_drawdown:.2%} | ${row.ending_value_usd:,.0f} | '
            f'${row.pnl_usd:,.0f} |'
        )
    return '\n'.join(rows)


def _write_readme(
    path: Path,
    summary: pd.DataFrame,
    manifest: dict,
) -> None:
    requested = summary.loc[summary['window'].eq('requested_1997_window')]
    table = _markdown_performance_table(requested)
    content = f'''# Portfolio Backtest Evidence: 1997 to {manifest['end_date'][:4]}

This package compares every investable portfolio output currently produced by the repository. Current-derived allocations start with the observed current NAV of ${manifest['current_portfolio_nav_usd']:,.0f}; independent clean-sheet, optimiser, and LLM portfolios start with $100,000.

> **Interpretation boundary:** the long history is a retrospective replay of today's selected holdings and weights. It contains selection look-ahead and survivorship bias and is not a 1997 point-in-time model backtest. The shorter reconstructed point-in-time model evidence is reported separately.

## Requested Window

{table}

## Evidence Included

- monthly adjusted-close returns converted to USD with historical FRED FX
- pre-listing and unallocated capital held at the 3-month Treasury-bill rate
- monthly rebalancing with commissions, spread, slippage, market impact, and ADV checks
- portfolio-specific regional index blends plus S&P 500 and SPY comparisons
- a lagged trend and risk-controlled regional-index challenger
- 36-month untouched embargo evaluation
- circular moving-block resampling and correlated fat-tailed Monte Carlo
- PSR, Minimum Track Record Length, Sidak FWER, and Deflated Sharpe Ratios
- HTML and PDF reports, source manifest, compact result tables, plots, and SHA-256 checksums

Open [backtest_report.html](backtest_report.html) for the complete rendered report. See [docs/BACKTEST_METHODOLOGY.md](../../../docs/BACKTEST_METHODOLOGY.md) for formulas, assumptions, and the paper-to-code mapping.

Raw provider histories are intentionally excluded from Git. This is research evidence, not authorization for live trading.
'''
    path.write_text(content, encoding='utf-8')


def _write_checksums(output_directory: Path) -> None:
    rows = []
    for path in sorted(output_directory.rglob('*')):
        if not path.is_file() or path.name == 'checksums.sha256':
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        relative = str(path.relative_to(output_directory)).replace(chr(92), '/')
        rows.append(f'{digest}  {relative}')
    (output_directory / 'checksums.sha256').write_text('\n'.join(rows) + '\n', encoding='ascii')


def write_backtest_outputs(
    output_directory: Path,
    frames: dict[str, pd.DataFrame],
    results: list[ReplayResult],
    config: dict,
    manifest: dict,
) -> dict[str, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    plot_directory = output_directory / 'plots'
    plot_directory.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        frame.to_csv(output_directory / f'{name}.csv', index=False)

    labels = {result.strategy: result.label for result in results}
    benchmark_labels = (
        frames['benchmark_monthly_returns'][['strategy', 'strategy_label']]
        .drop_duplicates('strategy')
        .set_index('strategy')['strategy_label']
        .to_dict()
    )
    labels.update(benchmark_labels)
    monthly = frames['monthly_returns']
    summary = frames['performance_summary']
    plot_wealth_paths(monthly, labels, plot_directory / 'wealth_paths.png')
    plot_benchmark_comparison(
        monthly,
        frames['benchmark_monthly_returns'],
        labels,
        plot_directory / 'benchmark_comparison.png',
    )
    plot_ending_pnl(summary, plot_directory / 'ending_pnl.png')
    plot_risk_return(summary, plot_directory / 'risk_return.png')
    plot_drawdowns(results, plot_directory / 'drawdowns.png')
    plot_annual_heatmap(frames['annual_returns'], labels, plot_directory / 'annual_returns.png')
    plot_interval_summary(
        frames['block_resampling_summary'],
        labels,
        plot_directory / 'block_resampling.png',
        'Moving-Block Resampling CAGR Distribution',
    )
    plot_interval_summary(
        frames['monte_carlo_summary'],
        labels,
        plot_directory / 'monte_carlo.png',
        'Correlated Student-t Monte Carlo CAGR Distribution',
    )
    plot_embargo(frames['embargo_comparison'], labels, plot_directory / 'embargo.png')
    plot_investable_starts(summary, plot_directory / 'investable_starts.png')
    plot_causal_graph(plot_directory / 'causal_graph.png')

    manifest_path = output_directory / 'run_manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str) + '\n', encoding='utf-8')
    requested = summary.loc[summary['window'].eq('requested_1997_window')].sort_values('sharpe', ascending=False)
    performance_table = _html_table(
        requested,
        ['strategy_label', 'initial_capital_usd', 'cagr', 'annualised_volatility', 'sharpe', 'maximum_drawdown', 'ending_value_usd', 'pnl_usd'],
        {
            'strategy_label': 'Portfolio',
            'initial_capital_usd': 'Start',
            'annualised_volatility': 'Volatility',
            'maximum_drawdown': 'Max drawdown',
            'ending_value_usd': 'Ending value',
            'pnl_usd': 'PnL',
        },
    )
    primary_benchmarks = {
        'common_index',
        'total_return_proxy',
        'equal_weight_regional_indices',
    }
    benchmark_performance = frames['benchmark_performance']
    benchmark_performance = benchmark_performance.loc[
        benchmark_performance['window'].eq('common_investable_window')
        & benchmark_performance['strategy'].isin(primary_benchmarks)
    ].sort_values('sharpe', ascending=False)
    benchmark_performance_table = _html_table(
        benchmark_performance,
        ['strategy_label', 'cagr', 'annualised_volatility', 'sharpe', 'maximum_drawdown', 'ending_value_usd'],
        {
            'strategy_label': 'Index benchmark',
            'annualised_volatility': 'Volatility',
            'maximum_drawdown': 'Max drawdown',
            'ending_value_usd': 'Ending value on $100k',
        },
    )
    benchmark_relative = frames['benchmark_relative_summary']
    benchmark_relative = benchmark_relative.loc[
        benchmark_relative['window'].eq('common_investable_window')
    ].sort_values('information_ratio', ascending=False)
    benchmark_table = _html_table(
        benchmark_relative,
        ['strategy_label', 'benchmark_label', 'annualised_alpha', 'beta', 'tracking_error', 'information_ratio', 'active_return_cumulative', 'relative_pnl_usd'],
        {
            'strategy_label': 'Portfolio',
            'benchmark_label': 'Regional benchmark',
            'relative_pnl_usd': 'Relative PnL',
        },
    )
    significance_table = _html_table(
        frames['statistical_significance'].sort_values('deflated_sharpe_ratio', ascending=False),
        ['strategy', 'annualised_sharpe', 'probabilistic_sharpe_ratio', 'minimum_track_record_months', 'sidak_significant', 'deflated_sharpe_ratio', 'cluster_adjusted_deflated_sharpe_ratio'],
        {'strategy': 'Portfolio', 'probabilistic_sharpe_ratio': 'PSR', 'minimum_track_record_months': 'MinTRL months', 'deflated_sharpe_ratio': 'DSR'},
    )
    limitation_table = _html_table(
        frames['bias_and_limitations'],
        ['category', 'severity', 'applies_to', 'status', 'treatment'],
    )
    pit_table = _html_table(
        frames.get('point_in_time_summary', pd.DataFrame()),
        ['strategy', 'observations', 'annualised_return', 'annualised_volatility', 'sharpe', 'maximum_drawdown', 'annualised_cost_drag', 'evidence_mode'],
    )
    execution_table = _html_table(
        frames['cost_liquidity_summary'].sort_values('total_transaction_cost_usd', ascending=False),
        ['strategy', 'total_transaction_cost_usd', 'annualised_turnover', 'maximum_adv_participation', 'liquidity_breach_count', 'maximum_unfilled_target_weight'],
        {
            'strategy': 'Portfolio',
            'total_transaction_cost_usd': 'Total modeled cost',
            'annualised_turnover': 'Annual turnover',
            'maximum_adv_participation': 'Max ADV participation',
            'liquidity_breach_count': 'Constrained trade events',
            'maximum_unfilled_target_weight': 'Max unfilled target',
        },
    )
    repair_table = _html_table(
        frames['price_quality_adjustments'],
        ['symbol', 'date', 'adjustment_type', 'raw_daily_return', 'repaired_daily_return', 'adjustment_factor'],
        {
            'date': 'Event date',
            'adjustment_type': 'Auditable repair',
            'raw_daily_return': 'Raw return',
            'repaired_daily_return': 'Post-repair return',
            'adjustment_factor': 'Scale factor',
        },
    )

    template_path = Path(__file__).parent / 'templates' / 'backtest_report.html.j2'
    template = Template(template_path.read_text(encoding='utf-8'))
    start_year = str(manifest['start_date'])[:4]
    end_year = str(manifest['end_date'])[:4]
    requested_years = float(manifest['requested_years'])
    current_nav = float(manifest['current_portfolio_nav_usd'])
    html = template.render(
        title=f'Portfolio Backtest Evidence: {start_year}-{end_year}',
        warning='The long-history portfolio results are retrospective holdings replays, not point-in-time stock-selection backtests. Use them for exposure and path diagnostics, not as evidence that the current model could have selected these names in 1997.',
        strategy_count=manifest['portfolio_output_count'],
        requested_years=f'{requested_years:.1f}',
        current_nav=f'${current_nav:,.0f}',
        common_start=manifest.get('common_investable_start', 'Not reached'),
        pit_months=manifest.get('point_in_time_months', 0),
        performance_table=performance_table,
        benchmark_performance_table=benchmark_performance_table,
        benchmark_table=benchmark_table,
        significance_table=significance_table,
        limitation_table=limitation_table,
        pit_table=pit_table,
        execution_table=execution_table,
        repair_table=repair_table,
    )
    html_path = output_directory / 'backtest_report.html'
    html_path.write_text(html, encoding='utf-8')
    pdf_path = output_directory / 'backtest_report.pdf'
    pdf_warning_path = output_directory / 'pdf_render_warning.txt'
    try:
        font_cache = Path(config['backtest']['cache_directory']) / 'fontconfig'
        font_config = configure_font_environment(font_cache)
        environment = os.environ.copy()
        environment['FONTCONFIG_FILE'] = str(font_config)
        completed = subprocess.run(
            [
                sys.executable,
                '-m',
                'src.backtesting.pdf_renderer',
                str(html_path),
                str(pdf_path),
            ],
            cwd=Path(config['_meta']['repository_root']),
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(detail or f'PDF renderer exited with {completed.returncode}.')
        if completed.stderr.strip():
            pdf_warning_path.write_text(completed.stderr, encoding='utf-8')
        elif pdf_warning_path.exists():
            pdf_warning_path.unlink()
    except Exception as exc:
        pdf_warning_path.write_text(
            f'PDF rendering failed: {type(exc).__name__}: {exc}\n',
            encoding='utf-8',
        )
    _write_readme(output_directory / 'README.md', summary, manifest)
    _write_checksums(output_directory)
    return {
        'output_directory': output_directory,
        'html_report': html_path,
        'pdf_report': pdf_path,
        'manifest': manifest_path,
    }
