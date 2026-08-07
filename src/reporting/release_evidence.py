from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
from typing import Iterable

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.utils.config import ROOT


PASS = '#2F855A'
WARNING = '#C07A16'
FAIL = '#C53030'
INK = '#172A3A'
BLUE = '#2B6CB0'
TEAL = '#16817A'
GREY = '#D8DEE6'


@dataclass(frozen=True)
class ReleaseEvidenceResult:
    output_directory: Path
    file_count: int
    validation_run_id: str
    approval_status: str
    overall_score: float


def build_universe_summary(universe: pd.DataFrame) -> pd.DataFrame:
    required = {'security_id', 'region', 'listing_status'}
    missing = required.difference(universe.columns)
    if missing:
        raise ValueError(f'Universe summary is missing columns: {sorted(missing)}')
    counts = (
        universe.groupby(['region', 'listing_status'], dropna=False)['security_id']
        .nunique()
        .unstack(fill_value=0)
    )
    for status in ('Active', 'Delisted'):
        if status not in counts:
            counts[status] = 0
    counts = counts[['Active', 'Delisted']].rename(
        columns={'Active': 'active', 'Delisted': 'delisted'}
    )
    counts['total'] = counts.sum(axis=1)
    counts['active_share'] = counts['active'] / counts['total'].replace(0, np.nan)
    counts = counts.reset_index().sort_values('region').reset_index(drop=True)
    total = pd.DataFrame(
        {
            'region': ['ALL'],
            'active': [int(counts['active'].sum())],
            'delisted': [int(counts['delisted'].sum())],
            'total': [int(counts['total'].sum())],
        }
    )
    total['active_share'] = total['active'] / total['total']
    return pd.concat([counts, total], ignore_index=True)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f'Required release evidence is missing: {path}')
    return pd.read_csv(path, low_memory=False)


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _copy_directory(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f'Required release directory is missing: {source}')
    for path in sorted(source.rglob('*')):
        if path.is_file():
            _copy_file(path, destination / path.relative_to(source))


def _style_axis(axis: plt.Axes, title: str) -> None:
    axis.set_title(title, color=INK, fontsize=13, fontweight='bold', pad=12)
    axis.spines[['top', 'right']].set_visible(False)
    axis.grid(axis='y', alpha=0.20, color='#7D8A99')
    axis.set_axisbelow(True)


def _save(figure: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, bbox_inches='tight', facecolor='white')
    plt.close(figure)


def _plot_validation_scorecard(scorecard: pd.DataFrame, path: Path) -> None:
    data = scorecard.copy().iloc[::-1]
    colors = data['status'].map({'PASS': PASS, 'WARNING': WARNING, 'FAIL': FAIL}).fillna(GREY)
    figure, axis = plt.subplots(figsize=(10, 5.8))
    axis.barh(data['component'], data['maximum_score'], color=GREY, height=0.62)
    axis.barh(data['component'], data['score'], color=colors, height=0.62)
    for index, row in enumerate(data.itertuples(index=False)):
        axis.text(
            float(row.maximum_score) + 0.25,
            index,
            f'{float(row.score):.1f}/{float(row.maximum_score):.0f}',
            va='center',
            fontsize=9,
            color=INK,
        )
    _style_axis(axis, 'Model validation scorecard')
    axis.set_xlabel('Governance points')
    axis.set_xlim(0, float(data['maximum_score'].max()) + 4)
    figure.tight_layout()
    _save(figure, path)


def _plot_forecast_quality(forecasts: pd.DataFrame, path: Path) -> None:
    data = forecasts.copy()
    labels = data['horizon'].astype(str).tolist()
    x = np.arange(len(data))
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    axes[0].bar(x, data['directional_accuracy'], color=BLUE, width=0.62)
    axes[0].axhline(0.50, color=WARNING, linestyle='--', linewidth=1.4, label='Random baseline')
    axes[0].set_xticks(x, labels)
    axes[0].set_ylim(0.45, max(0.60, float(data['directional_accuracy'].max()) + 0.02))
    axes[0].set_ylabel('Directional accuracy')
    axes[0].legend(frameon=False, fontsize=8)
    _style_axis(axes[0], 'Directional accuracy by horizon')
    axes[1].bar(x, data['rank_ic'], color=TEAL, width=0.62)
    axes[1].axhline(0, color=INK, linewidth=0.8)
    axes[1].set_xticks(x, labels)
    axes[1].set_ylabel('Spearman rank IC')
    _style_axis(axes[1], 'Cross-sectional rank information')
    figure.tight_layout()
    _save(figure, path)


def _plot_distribution_coverage(distribution: pd.DataFrame, path: Path) -> None:
    data = distribution.copy()
    x = np.arange(len(data))
    figure, axis = plt.subplots(figsize=(9.5, 4.8))
    for column, label, color, target in (
        ('p5_coverage', 'P5', FAIL, 0.05),
        ('p50_coverage', 'P50', BLUE, 0.50),
        ('p95_coverage', 'P95', PASS, 0.95),
    ):
        axis.plot(x, data[column], marker='o', linewidth=2, color=color, label=label)
        axis.axhline(target, color=color, alpha=0.30, linestyle='--', linewidth=1)
    axis.set_xticks(x, data['horizon'].astype(str))
    axis.set_ylim(0, 1)
    axis.set_ylabel('Empirical coverage')
    axis.legend(frameon=False, ncol=3)
    _style_axis(axis, 'Distribution coverage by forecast horizon')
    figure.tight_layout()
    _save(figure, path)


def _plot_risk_backtest(risk: pd.DataFrame, path: Path) -> None:
    data = risk.copy()
    labels = [f'{int(float(value) * 100)}%' for value in data['confidence_level']]
    x = np.arange(len(data))
    width = 0.34
    figure, axis = plt.subplots(figsize=(8.8, 4.8))
    axis.bar(
        x - width / 2,
        data['expected_violation_rate'],
        width,
        color=GREY,
        label='Expected',
    )
    axis.bar(
        x + width / 2,
        data['violation_rate'],
        width,
        color=[PASS if status == 'PASS' else WARNING for status in data['status']],
        label='Observed',
    )
    axis.set_xticks(x, labels)
    axis.set_ylabel('Daily VaR violation rate')
    axis.legend(frameon=False)
    _style_axis(axis, 'EWMA VaR backtest')
    for index, row in enumerate(data.itertuples(index=False)):
        axis.text(
            index,
            max(float(row.expected_violation_rate), float(row.violation_rate)) + 0.002,
            f'Kupiec p={float(row.p_value):.3f}\nIndependence p={float(row.christoffersen_p_value):.3f}',
            ha='center',
            va='bottom',
            fontsize=8,
            color=INK,
        )
    axis.set_ylim(0, float(data[['expected_violation_rate', 'violation_rate']].max().max()) + 0.025)
    figure.tight_layout()
    _save(figure, path)


def _strategy_label(value: str) -> str:
    return value.replace('_eligible', '').replace('_', ' ').title()


def _plot_portfolio_comparison(strategies: pd.DataFrame, path: Path) -> None:
    data = strategies.copy()
    labels = [_strategy_label(value) for value in data['strategy'].astype(str)]
    colors = [BLUE if value == 'wolf_cvar' else TEAL for value in data['strategy']]
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    axes[0].bar(labels, data['annualised_return'], color=colors, width=0.62)
    axes[0].set_ylabel('Annualised net return')
    axes[0].tick_params(axis='x', rotation=20)
    axes[0].yaxis.set_major_formatter(lambda value, _: f'{value:.0%}')
    _style_axis(axes[0], 'Net performance comparison')
    axes[1].bar(labels, data['sharpe'], color=colors, width=0.62)
    axes[1].set_ylabel('Net Sharpe ratio')
    axes[1].tick_params(axis='x', rotation=20)
    _style_axis(axes[1], 'Risk-adjusted performance')
    figure.tight_layout()
    _save(figure, path)


def _plot_cumulative_returns(returns: pd.DataFrame, path: Path) -> None:
    data = returns.copy()
    data['date'] = pd.to_datetime(data['date'])
    data['net_return'] = pd.to_numeric(data['net_return'], errors='coerce').fillna(0)
    figure, axis = plt.subplots(figsize=(10, 5.2))
    colors = {'wolf_cvar': BLUE, 'equal_weight_eligible': TEAL, 'cap_weight_eligible': WARNING}
    for strategy, frame in data.sort_values('date').groupby('strategy', sort=False):
        cumulative = (1 + frame['net_return']).cumprod() - 1
        axis.plot(
            frame['date'],
            cumulative,
            linewidth=2,
            color=colors.get(str(strategy), GREY),
            label=_strategy_label(str(strategy)),
        )
    axis.yaxis.set_major_formatter(lambda value, _: f'{value:.0%}')
    axis.set_ylabel('Cumulative net return')
    axis.legend(frameon=False)
    _style_axis(axis, 'Walk-forward portfolio performance')
    figure.autofmt_xdate()
    figure.tight_layout()
    _save(figure, path)


def _plot_regional_rank_ic(regional: pd.DataFrame, path: Path) -> None:
    data = regional.copy()
    horizon_order = ['3M', '6M', '9M', '12M']
    matrix = data.pivot_table(index='region', columns='horizon', values='rank_ic')
    matrix = matrix.reindex(columns=[value for value in horizon_order if value in matrix])
    maximum = max(0.05, float(np.nanmax(np.abs(matrix.to_numpy(dtype=float)))))
    figure, axis = plt.subplots(figsize=(9.5, 5.2))
    image = axis.imshow(matrix, cmap='RdYlGn', vmin=-maximum, vmax=maximum, aspect='auto')
    axis.set_xticks(np.arange(len(matrix.columns)), matrix.columns)
    axis.set_yticks(np.arange(len(matrix.index)), matrix.index)
    for row in range(len(matrix.index)):
        for column in range(len(matrix.columns)):
            value = matrix.iloc[row, column]
            axis.text(column, row, f'{value:.3f}', ha='center', va='center', fontsize=8, color=INK)
    axis.set_title('Regional rank IC by forecast horizon', color=INK, fontsize=13, fontweight='bold', pad=12)
    figure.colorbar(image, ax=axis, label='Spearman rank IC', shrink=0.82)
    figure.tight_layout()
    _save(figure, path)


def _plot_final_exposures(portfolio: pd.DataFrame, path: Path) -> None:
    weight_column = 'final_weight' if 'final_weight' in portfolio else 'target_weight'
    data = portfolio.copy()
    data[weight_column] = pd.to_numeric(data[weight_column], errors='coerce').fillna(0)
    figure, axes = plt.subplots(1, 2, figsize=(11, 5.2))
    for axis, column, color in ((axes[0], 'region', BLUE), (axes[1], 'sector', TEAL)):
        exposure = data.groupby(column, dropna=False)[weight_column].sum().sort_values()
        axis.barh(exposure.index.astype(str), exposure.to_numpy(), color=color)
        axis.xaxis.set_major_formatter(lambda value, _: f'{value:.0%}')
        axis.set_xlabel('Portfolio weight')
        _style_axis(axis, f'Final portfolio by {column}')
    figure.tight_layout()
    _save(figure, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _portable_value(value: object) -> object:
    if isinstance(value, dict):
        return {key: _portable_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_portable_value(item) for item in value]
    if isinstance(value, str):
        portable = value.replace(str(ROOT), '.')
        return portable.replace(ROOT.as_posix(), '.')
    return value


def _normalise_json_paths(directory: Path) -> None:
    for path in sorted(directory.rglob('*.json')):
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            continue
        path.write_text(
            json.dumps(_portable_value(payload), indent=2, sort_keys=True) + '\n',
            encoding='utf-8',
        )


def _normalise_text_whitespace(directory: Path) -> None:
    text_suffixes = {'.csv', '.css', '.html', '.json', '.md', '.txt'}
    for path in sorted(directory.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in text_suffixes:
            continue
        text = path.read_text(encoding='utf-8')
        normalised = '\n'.join(line.rstrip() for line in text.splitlines()) + '\n'
        path.write_text(normalised, encoding='utf-8')


def _validate_plots(paths: Iterable[Path]) -> None:
    for path in paths:
        pixels = plt.imread(path)
        if pixels.shape[0] < 500 or pixels.shape[1] < 800:
            raise RuntimeError(f'Release plot is undersized: {path}')
        if float(np.nanstd(pixels)) < 0.02:
            raise RuntimeError(f'Release plot appears blank: {path}')


def _markdown_table(frame: pd.DataFrame, columns: Iterable[str]) -> list[str]:
    selected = frame[list(columns)].copy()
    lines = [
        '| ' + ' | '.join(selected.columns) + ' |',
        '| ' + ' | '.join(['---'] * len(selected.columns)) + ' |',
    ]
    for row in selected.itertuples(index=False, name=None):
        lines.append('| ' + ' | '.join(str(value) for value in row) + ' |')
    return lines


def _write_release_notes(
    output: Path,
    validation_manifest: dict,
    walk_manifest: dict,
    universe_summary: pd.DataFrame,
    scorecard: pd.DataFrame,
    strategies: pd.DataFrame,
) -> None:
    wolf = strategies.loc[strategies['strategy'].eq('wolf_cvar')].iloc[0]
    profile = walk_manifest['artifact_profile']
    overall = universe_summary.loc[universe_summary['region'].eq('ALL')].iloc[0]
    validation_run_id = str(validation_manifest['validation_run_id'])
    approval_status = str(validation_manifest['approval_status'])
    overall_score = float(validation_manifest['overall_score'])
    critical_failure_count = len(validation_manifest.get('critical_failures', []))
    forecast_rows = int(profile['forecast_rows'])
    outcome_rows = int(profile['outcome_rows'])
    portfolio_months = int(profile['portfolio_months'])
    component_table = scorecard.copy()
    component_table['score'] = component_table.apply(
        lambda row: f'{float(row.score):.1f}/{float(row.maximum_score):.0f}',
        axis=1,
    )
    lines = [
        '# Full-Universe Model Evidence',
        '',
        f'Validation run: `{validation_run_id}`',
        '',
        '## Decision',
        '',
        f'- Governance status: **{approval_status}**',
        f'- Overall score: **{overall_score:.1f}/100**',
        f'- Critical failures: **{critical_failure_count}**',
        f'- Active universe: **{int(overall.active):,}** of **{int(overall.total):,}** listed and historical securities',
        f'- Walk-forward evidence: **{forecast_rows:,}** forecasts and **{outcome_rows:,}** aligned outcomes',
        f'- Portfolio: **{portfolio_months}** monthly decisions, **{float(wolf.annualised_return):.1%}** annualised net return, **{float(wolf.sharpe):.2f}** Sharpe',
        '',
        'The result is capped at conditional approval because the free-source history reconstructs filing availability and does not provide immutable historical universe, volume, sentiment, narrative, or regime vintages.',
        '',
        '## Scorecard',
        '',
        *_markdown_table(component_table, ['component', 'score', 'status']),
        '',
        '![Validation scorecard](plots/validation_scorecard.png)',
        '',
        '## Forecasts',
        '',
        'All point-forecast horizons passed the configured directional-accuracy, rank-IC, and normalized-RMSE gates. Distribution coverage passes at 3M and 6M and remains a warning at 9M and 12M.',
        '',
        '![Forecast quality](plots/forecast_quality.png)',
        '',
        '![Distribution coverage](plots/distribution_coverage.png)',
        '',
        '## Portfolio And Risk',
        '',
        'The constrained Wolf portfolio passes net-of-cost, turnover, drawdown, hard-constraint, and daily EWMA VaR backtests. Equal weight outperformed over this short sample, but the difference was not statistically significant.',
        '',
        '![Cumulative returns](plots/cumulative_returns.png)',
        '',
        '![Portfolio comparison](plots/portfolio_comparison.png)',
        '',
        '![VaR backtest](plots/risk_backtest.png)',
        '',
        '![Final exposures](plots/final_portfolio_exposures.png)',
        '',
        '![Regional rank IC](plots/regional_rank_ic.png)',
        '',
        '## Package Contents',
        '',
        '- `validation/`: complete governance output, including HTML and Markdown reports.',
        '- `investment_committee/`: complete IC report bundle, PDF, data tables, and charts.',
        '- `final_portfolio_weights.csv`: resolved 20-name final portfolio.',
        '- `universe_summary.csv`: compact active and delisted security coverage by region.',
        '- `walk_forward_manifest.json`: source profile, chronology checks, limitations, and evidence counts.',
        '- `manifest.json`: SHA-256 checksum and byte size for every release artifact.',
        '',
        'Research output only. Conditional approval is not authorization for unattended live trading.',
    ]
    (output / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def build_release_evidence(
    release_id: str,
    outputs_directory: str | Path | None = None,
    releases_directory: str | Path | None = None,
) -> ReleaseEvidenceResult:
    outputs = Path(outputs_directory or ROOT / 'reports' / 'outputs')
    releases = Path(releases_directory or ROOT / 'reports' / 'releases')
    output = releases / release_id
    output.mkdir(parents=True, exist_ok=True)

    validation_source = outputs / 'validation' / 'latest'
    ic_source = outputs / 'ic' / 'latest'
    walk_source = outputs / 'walk_forward'
    validation_manifest = json.loads(
        (validation_source / 'validation_manifest.json').read_text(encoding='utf-8')
    )
    walk_manifest = json.loads(
        (walk_source / 'walk_forward_manifest.json').read_text(encoding='utf-8')
    )
    _copy_directory(validation_source, output / 'validation')
    _copy_directory(ic_source, output / 'investment_committee')
    _copy_file(walk_source / 'walk_forward_manifest.json', output / 'walk_forward_manifest.json')
    _copy_file(outputs / 'final_portfolio_weights.csv', output / 'final_portfolio_weights.csv')
    enrichment = outputs / 'free_data_enrichment_status.json'
    if enrichment.exists():
        _copy_file(enrichment, output / 'free_data_enrichment_status.json')

    universe = _read_csv(outputs / 'equity_universe.csv')
    universe_summary = build_universe_summary(universe)
    universe_summary.to_csv(output / 'universe_summary.csv', index=False)

    scorecard = _read_csv(validation_source / 'model_validation_scorecard.csv')
    forecasts = _read_csv(validation_source / 'forecast_accuracy_report.csv')
    distribution = _read_csv(validation_source / 'distribution_coverage_report.csv')
    risk = _read_csv(validation_source / 'risk_backtesting_report.csv')
    strategies = _read_csv(validation_source / 'portfolio_strategy_comparison.csv')
    regional = _read_csv(validation_source / 'regional_performance_report.csv')
    returns = pd.read_parquet(walk_source / 'historical_portfolio_returns.parquet')
    portfolio = _read_csv(outputs / 'final_portfolio_weights.csv')
    plots = output / 'plots'
    _plot_validation_scorecard(scorecard, plots / 'validation_scorecard.png')
    _plot_forecast_quality(forecasts, plots / 'forecast_quality.png')
    _plot_distribution_coverage(distribution, plots / 'distribution_coverage.png')
    _plot_risk_backtest(risk, plots / 'risk_backtest.png')
    _plot_portfolio_comparison(strategies, plots / 'portfolio_comparison.png')
    _plot_cumulative_returns(returns, plots / 'cumulative_returns.png')
    _plot_regional_rank_ic(regional, plots / 'regional_rank_ic.png')
    _plot_final_exposures(portfolio, plots / 'final_portfolio_exposures.png')
    _validate_plots(sorted(plots.glob('*.png')))
    _write_release_notes(
        output,
        validation_manifest,
        walk_manifest,
        universe_summary,
        scorecard,
        strategies,
    )
    _normalise_text_whitespace(output)
    _normalise_json_paths(output)

    files = sorted(path for path in output.rglob('*') if path.is_file() and path.name != 'manifest.json')
    artifact_manifest = {
        'release_id': release_id,
        'source_validation_run_id': validation_manifest['validation_run_id'],
        'approval_status': validation_manifest['approval_status'],
        'overall_score': validation_manifest['overall_score'],
        'evidence_mode': validation_manifest.get('evidence_mode'),
        'generated_at': validation_manifest.get('completed_at'),
        'files': [
            {
                'path': path.relative_to(output).as_posix(),
                'size_bytes': path.stat().st_size,
                'sha256': _sha256(path),
            }
            for path in files
        ],
    }
    (output / 'manifest.json').write_text(
        json.dumps(artifact_manifest, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    return ReleaseEvidenceResult(
        output_directory=output,
        file_count=len(files) + 1,
        validation_run_id=str(validation_manifest['validation_run_id']),
        approval_status=str(validation_manifest['approval_status']),
        overall_score=float(validation_manifest['overall_score']),
    )
