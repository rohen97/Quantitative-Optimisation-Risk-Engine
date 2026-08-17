from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.models.supervised_alpha import (
    ARTIFACT_VERSION,
    SupervisedAlphaResult,
    SupervisedAlphaSettings,
)
from src.utils.config import ROOT


MODEL_COLOURS = {
    'linear': '#2f6f8f',
    'tree': '#b45f3c',
    'ranker': '#3f7d4a',
    'ensemble': '#242424',
}


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(content, encoding='utf-8')
    temporary.replace(path)


def _atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def _atomic_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    frame.to_parquet(temporary, index=False, compression='zstd')
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonable(value: Any) -> Any:
    if value is pd.NaT:
        return None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    return value


def _portable_path(value: str | Path) -> str:
    path = Path(value)
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _portable_value(value: Any) -> Any:
    if isinstance(value, Path):
        return _portable_path(value)
    if isinstance(value, str):
        root = str(ROOT.resolve())
        if value == root or value.startswith(root + '\\') or value.startswith(root + '/'):
            return _portable_path(value)
        return value
    if isinstance(value, (list, tuple, set)):
        return [_portable_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _portable_value(item) for key, item in value.items()}
    return value


def load_supervised_alpha_artifacts(output: str | Path) -> SupervisedAlphaResult:
    """Load a completed table set so reporting can be safely resealed."""

    directory = Path(output)

    def csv(name: str) -> pd.DataFrame:
        path = directory / name
        return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()

    prediction_path = directory / 'oos_predictions.parquet'
    return SupervisedAlphaResult(
        dataset_profile=csv('dataset_profile.csv'),
        validation_summary=csv('validation_summary.csv'),
        family_winners=csv('family_winners.csv'),
        ensemble_weights=csv('ensemble_weights.csv'),
        validation_monthly=csv('validation_monthly.csv'),
        oos_summary=csv('oos_summary.csv'),
        oos_monthly=csv('oos_monthly.csv'),
        oos_predictions=(
            pd.read_parquet(prediction_path) if prediction_path.exists() else pd.DataFrame()
        ),
        ols_screening=csv('ols_screening.csv'),
        quantile_metrics=csv('quantile_metrics.csv'),
        generalisation_audit=csv('generalisation_audit.csv'),
        latest_predictions=csv('latest_predictions.csv'),
        acceptance_decision=csv('acceptance_decision.csv'),
        model_manifest=csv('model_manifest.csv'),
        failures=csv('model_failures.csv'),
    )


def _markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return 'No observations were available.'
    visible = frame[[column for column in columns if column in frame]].copy()
    for column in visible.select_dtypes(include='number'):
        visible[column] = visible[column].map(
            lambda value: '' if pd.isna(value) else f'{float(value):.4f}'
        )
    headers = visible.columns.tolist()
    lines = [
        '| ' + ' | '.join(headers) + ' |',
        '| ' + ' | '.join(['---'] * len(headers)) + ' |',
    ]
    for row in visible.astype(str).itertuples(index=False, name=None):
        lines.append('| ' + ' | '.join(value.replace('|', '\\|') for value in row) + ' |')
    return '\n'.join(lines)


def _plot_validation(result: SupervisedAlphaResult, path: Path) -> None:
    data = result.family_winners.copy()
    ensemble = result.validation_summary.loc[
        result.validation_summary['candidate'].eq('supervised_alpha_ensemble')
    ].copy()
    data = pd.concat([data, ensemble], ignore_index=True)
    if data.empty:
        return
    horizons = sorted(data['horizon_months'].unique())
    fig, axes = plt.subplots(1, len(horizons), figsize=(4.2 * len(horizons), 4.6), squeeze=False)
    for axis, horizon in zip(axes[0], horizons):
        subset = data.loc[data['horizon_months'].eq(horizon)].sort_values('mean_rank_ic')
        labels = subset['family'].astype(str)
        colours = [MODEL_COLOURS.get(category, '#777777') for category in subset['category']]
        axis.barh(labels, subset['mean_rank_ic'], color=colours)
        axis.axvline(0.0, color='#555555', linewidth=0.8)
        axis.set_title(f'{int(horizon)}-month horizon')
        axis.set_xlabel('Validation mean rank IC')
        axis.grid(axis='x', alpha=0.2)
    fig.suptitle('Supervised Alpha Validation by Model Family', fontsize=14)
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches='tight')
    plt.close(fig)


def _plot_oos_paths(result: SupervisedAlphaResult, path: Path) -> None:
    data = result.oos_monthly.loc[
        result.oos_monthly['candidate'].eq('supervised_alpha_ensemble')
    ].copy()
    if data.empty:
        return
    data['as_of_date'] = pd.to_datetime(data['as_of_date'], errors='coerce')
    fig, axis = plt.subplots(figsize=(10.5, 5.2))
    colours = ['#2f6f8f', '#b45f3c', '#3f7d4a', '#7b5c99']
    for colour, (horizon, group) in zip(colours, data.groupby('horizon_months', sort=True)):
        ordered = group.sort_values('as_of_date')
        path_values = ordered['net_active_return'].cumsum()
        axis.plot(ordered['as_of_date'], path_values, label=f'{int(horizon)}m', color=colour, linewidth=2)
    axis.axhline(0.0, color='#555555', linewidth=0.8)
    axis.set_title('Legacy OOS Cumulative Decision-Cohort Active Return')
    axis.set_ylabel('Cumulative net active return (cohort sum)')
    axis.set_xlabel('Decision date')
    axis.grid(alpha=0.2)
    axis.legend(title='Forecast horizon')
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches='tight')
    plt.close(fig)


def _plot_oos_rank_ic(result: SupervisedAlphaResult, path: Path) -> None:
    data = result.oos_monthly.loc[
        result.oos_monthly['candidate'].eq('supervised_alpha_ensemble')
    ].copy()
    if data.empty:
        return
    data['as_of_date'] = pd.to_datetime(data['as_of_date'], errors='coerce')
    horizons = sorted(data['horizon_months'].unique())
    fig, axes = plt.subplots(len(horizons), 1, figsize=(10.5, 2.4 * len(horizons)), sharex=True, squeeze=False)
    for axis, horizon in zip(axes[:, 0], horizons):
        subset = data.loc[data['horizon_months'].eq(horizon)].sort_values('as_of_date')
        colours = np.where(subset['rank_ic'].ge(0), '#3f7d4a', '#b45f3c')
        axis.bar(subset['as_of_date'], subset['rank_ic'], width=20, color=colours)
        axis.axhline(0.0, color='#555555', linewidth=0.8)
        axis.set_ylabel(f'{int(horizon)}m IC')
        axis.grid(axis='y', alpha=0.2)
    axes[-1, 0].set_xlabel('Decision date')
    fig.suptitle('Legacy OOS Monthly Rank Information Coefficient', fontsize=14)
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches='tight')
    plt.close(fig)


def _report_text(result: SupervisedAlphaResult) -> str:
    overall = result.acceptance_decision.loc[
        result.acceptance_decision['scope'].eq('overall')
    ]
    if overall.empty:
        status = 'NOT EVALUATED'
        reason = 'No overall acceptance row was produced.'
    else:
        status = str(overall.iloc[0]['status'])
        reason = str(overall.iloc[0]['reasons'] or 'All configured gates passed.')
    oos_ensemble = result.oos_summary.loc[
        result.oos_summary['candidate'].eq('supervised_alpha_ensemble')
    ].sort_values('horizon_months')
    turnover_source = result.oos_monthly.loc[
        result.oos_monthly['candidate'].eq('supervised_alpha_ensemble')
    ].copy()
    turnover_rows: list[dict[str, Any]] = []
    for horizon, rows in turnover_source.groupby('horizon_months', sort=True):
        recurring = rows.loc[~rows['is_initial_funding'].fillna(False)]
        budget = pd.to_numeric(rows.get('turnover_budget'), errors='coerce')
        turnover = pd.to_numeric(rows.get('turnover'), errors='coerce')
        turnover_rows.append(
            {
                'horizon_months': horizon,
                'recurring_observations': len(recurring),
                'maximum_monthly_turnover': pd.to_numeric(
                    recurring.get('turnover'), errors='coerce'
                ).max(),
                'monthly_turnover_budget': budget.max(),
                'maximum_mandatory_exit_turnover': pd.to_numeric(
                    rows.get('mandatory_exit_turnover'), errors='coerce'
                ).max(),
                'maximum_cash_weight': pd.to_numeric(
                    rows.get('cash_weight'), errors='coerce'
                ).max(),
                'budget_breaches': int(
                    (
                        ~rows['is_initial_funding'].fillna(False)
                        & turnover.gt(budget + 1e-12)
                    ).sum()
                ),
            }
        )
    turnover_control = pd.DataFrame(turnover_rows)
    validation_ensemble = result.validation_summary.loc[
        result.validation_summary['candidate'].eq('supervised_alpha_ensemble')
    ].sort_values('horizon_months')
    quantiles = result.quantile_metrics.sort_values('horizon_months')
    failures = result.failures
    return f"""# Supervised Alpha Challenger Report

Generated: {datetime.now(UTC).isoformat()}

## Decision

**{status}**. {reason}

The supervised models remain governed challengers. A rejected or insufficient-evidence result sets the live deployment blend to zero, so the established regional-alpha optimiser remains unchanged.

## Dataset

{_markdown_table(result.dataset_profile, ['horizon_months', 'rows', 'securities', 'decision_dates', 'start_date', 'end_date', 'latest_target_date', 'minimum_outcome_cross_section_coverage', 'evidence_modes', 'numeric_features'])}

Each row joins features available at a historical decision date to a later realised return. Labels are measured relative to contemporaneous regional and sector peers. Decision dates with less than 90% realised-outcome coverage are excluded so an incomplete final cross-section cannot create forced sales or biased performance. The current panel is a reconstructed point-in-time proxy rather than native live evidence, so it is suitable for research but cannot authorize deployment.

## Validation

{_markdown_table(validation_ensemble, ['horizon_months', 'observations', 'independent_observations', 'mean_rank_ic', 'independent_rank_ic_hit_rate', 'independent_rank_ic_sign_test_p_value', 'mean_horizon_net_active_return', 'annualised_turnover', 'annualised_cost_drag', 'active_return_ci_lower_95'])}

Expanding-window folds use only labels whose target date is earlier than the next validation block. Validation labels must also mature before the legacy OOS start, preventing model-family selection from seeing any return realised inside that later calendar. Imputation, encoding, scaling, winsorisation, OLS screening, and model fitting are repeated inside each training fold.

## Legacy OOS

{_markdown_table(oos_ensemble, ['horizon_months', 'observations', 'independent_observations', 'mean_rank_ic', 'independent_rank_ic_hit_rate', 'independent_rank_ic_sign_test_p_value', 'mean_horizon_net_active_return', 'initial_funding_turnover', 'annualised_turnover', 'annualised_transaction_cost_drag', 'annualised_bank_fee_drag', 'annualised_cost_drag', 'active_return_ci_lower_95', 'active_return_ci_upper_95'])}

The monthly decision cohorts are scored separately but their forward return windows overlap. `independent_observations` counts a deterministic non-overlapping subset. Formal Sharpe ratios, t-statistics, confidence intervals and annualised return are suppressed until twelve independent cohorts exist; the independent sign-test p-value is shown instead. Recurring turnover excludes initial portfolio funding, which is reported separately. Desired weights move through an ex-ante 1.5x annual turnover budget; mandatory exits that exceed the monthly budget are disclosed rather than hidden. Net return and annual cost drag include the 0.25% annual bank charge in addition to spread, FX and impact estimates. This record has already informed research iteration, so it is labelled legacy OOS rather than untouched evidence; the cumulative plot is a cohort sum, not a CAGR or compound portfolio claim.

### Turnover Control Audit

{_markdown_table(turnover_control, ['horizon_months', 'recurring_observations', 'maximum_monthly_turnover', 'monthly_turnover_budget', 'maximum_mandatory_exit_turnover', 'maximum_cash_weight', 'budget_breaches'])}

The 12-month horizon has no recurring OOS rebalance, so its ongoing turnover remains unestimable. A temporary cash weight can arise when a previously held security lacks a valid next-period outcome; the model exits that name rather than inventing a return. Passing interval coverage does not imply precise forecasts: the 9- and 12-month bands remain very wide and should be treated as low-confidence risk bounds.

## Model Selection

{_markdown_table(result.ensemble_weights, ['horizon_months', 'candidate', 'family', 'category', 'ensemble_weight'])}

At most one positive-validation model from each of the linear, tree, and ranking categories enters the equal-weight ensemble. This limits meta-model flexibility and reduces another source of overfitting.

## Quantiles

{_markdown_table(quantiles, ['horizon_months', 'observations', 'calibration_method', 'calibration_dates', 'calibration_target_coverage', 'lower_coverage', 'central_90_coverage', 'upper_coverage', 'mean_interval_width', 'pinball_loss_q05', 'pinball_loss_q50', 'pinball_loss_q95'])}

The 5th, 50th, and 95th percentile forecasts are trained on an earlier development slice with histogram gradient boosting. A later purged development block applies date-block conformal interval correction and median-bias calibration before legacy OOS evaluation. The calibration block uses a conservative 95% target as a buffer around the published central 90% interval. Coverage shows how often realised benchmark-relative returns landed inside the calibrated interval.

## Generalisation Audit

{_markdown_table(result.generalisation_audit, ['horizon_months', 'validation_folds', 'validation_independent_observations', 'legacy_oos_independent_observations', 'validation_mean_rank_ic', 'legacy_oos_mean_rank_ic', 'rank_ic_retention_ratio', 'validation_mean_net_active_return', 'legacy_oos_mean_net_active_return', 'overfitting_signal', 'deployment_interpretation'])}

This comparison checks whether performance deteriorated after validation. A favourable legacy result is encouraging but cannot disprove overfitting because this holdout has been inspected and the feature history is reconstructed. Only the prospective shadow record can provide new falsification evidence.

## Acceptance Gates

{_markdown_table(result.acceptance_decision, ['scope', 'status', 'oos_monthly_observations', 'oos_observations', 'deployment_blend_weight', 'reasons'])}

`oos_observations` is the non-overlapping count used by governance. Promotion requires twelve genuinely prospective independent observations, a significant independent sign test, native point-in-time evidence, positive net active return, an estimable positive block-bootstrap lower confidence bound, and recurring annual turnover no greater than 1.5x. The legacy OOS record can never promote a model.

## Evidence Still Requiring New Data

No code change can make an inspected holdout untouched or turn reconstructed snapshots into native point-in-time facts. Deployment still requires future shadow outcomes, original filing/vintage timestamps, historical membership and inactive-security mappings, broader annual fundamentals and observed execution fills. These gaps remain explicit rather than being filled with current values or synthetic history.

## Failures

{_markdown_table(failures, ['horizon_months', 'split', 'fold', 'candidate', 'error'])}
"""


def write_supervised_alpha_artifacts(
    result: SupervisedAlphaResult,
    settings: SupervisedAlphaSettings,
    *,
    source_artifacts: dict[str, Any] | None = None,
) -> Path:
    output = settings.output_directory
    plots = output / 'plots'
    output.mkdir(parents=True, exist_ok=True)
    plots.mkdir(parents=True, exist_ok=True)
    model_manifest = result.model_manifest.copy()
    if 'model_path' in model_manifest:
        model_manifest['model_path'] = model_manifest['model_path'].map(_portable_path)
    tables = {
        'dataset_profile.csv': result.dataset_profile,
        'validation_summary.csv': result.validation_summary,
        'family_winners.csv': result.family_winners,
        'ensemble_weights.csv': result.ensemble_weights,
        'validation_monthly.csv': result.validation_monthly,
        'oos_summary.csv': result.oos_summary,
        'oos_monthly.csv': result.oos_monthly,
        'ols_screening.csv': result.ols_screening,
        'quantile_metrics.csv': result.quantile_metrics,
        'generalisation_audit.csv': result.generalisation_audit,
        'latest_predictions.csv': result.latest_predictions,
        'acceptance_decision.csv': result.acceptance_decision,
        'model_manifest.csv': model_manifest,
        'model_failures.csv': result.failures,
    }
    for filename, frame in tables.items():
        _atomic_csv(output / filename, frame)
    _atomic_parquet(output / 'oos_predictions.parquet', result.oos_predictions)
    _atomic_text(output / 'supervised_alpha_report.md', _report_text(result))
    _plot_validation(result, plots / 'validation_model_comparison.png')
    _plot_oos_paths(result, plots / 'oos_active_cohort_paths.png')
    _plot_oos_rank_ic(result, plots / 'oos_rank_ic.png')

    independently_frozen = {'prospective_freeze_manifest.json'}
    payload_files = sorted(
        path
        for path in output.rglob('*')
        if path.is_file()
        and path.name
        not in {'checksums.sha256', 'run_manifest.json', *independently_frozen}
    )
    checksums = [f'{_sha256(path)}  {path.relative_to(output).as_posix()}' for path in payload_files]
    _atomic_text(output / 'checksums.sha256', '\n'.join(checksums) + '\n')
    manifest = {
        'artifact_version': ARTIFACT_VERSION,
        'generated_at': datetime.now(UTC).isoformat(),
        'status': str(
            result.acceptance_decision.loc[
                result.acceptance_decision['scope'].eq('overall'), 'status'
            ].iloc[0]
        ),
        'settings': _jsonable(_portable_value(asdict(settings))),
        'source_artifacts': _jsonable(_portable_value(source_artifacts or {})),
        'payload_files': len(payload_files),
        'checksums_file': 'checksums.sha256',
        'model_bundles': model_manifest.to_dict(orient='records'),
    }
    _atomic_text(
        output / 'run_manifest.json',
        json.dumps(_jsonable(manifest), indent=2, sort_keys=True) + '\n',
    )
    return output
