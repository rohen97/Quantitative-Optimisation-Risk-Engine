from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.utils.config import ROOT
from src.validation.models import ValidationDataPackage, ValidationIssue


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _read_parquet(path: Path) -> pd.DataFrame:
    try:
        return pd.read_parquet(path) if path.exists() else pd.DataFrame()
    except (ImportError, OSError, ValueError):
        return pd.DataFrame()


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        return {}


def _historical_forecasts(
    walk_forward_directory: Path,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, dict]:
    historical = _read_parquet(
        walk_forward_directory / 'historical_forecasts.parquet'
    )
    outcomes = _read_parquet(
        walk_forward_directory / 'historical_realised_outcomes.parquet'
    )
    manifest = _read_json(walk_forward_directory / 'walk_forward_manifest.json')
    forecasts: dict[str, pd.DataFrame] = {}
    if historical.empty:
        return forecasts, outcomes, manifest
    historical['as_of_date'] = pd.to_datetime(historical['as_of_date'])
    historical['forecast_date'] = historical['as_of_date']
    historical['horizon'] = historical['horizon'].astype(str).str.upper()
    for horizon, frame in historical.groupby('horizon', sort=False):
        forecasts[str(horizon)] = frame.reset_index(drop=True)
    return forecasts, outcomes, manifest


def _current_forecasts(
    outputs: Path,
    as_of_date: pd.Timestamp,
) -> dict[str, pd.DataFrame]:
    forecasts: dict[str, pd.DataFrame] = {}
    for horizon in ('3M', '6M', '9M', '12M'):
        frame = _read_csv(outputs / f'ml_forecasts_{horizon.lower()}.csv')
        if frame.empty:
            continue
        frame['forecast_date'] = pd.to_datetime(frame.get('as_of_date', as_of_date))
        frame['as_of_date'] = frame['forecast_date']
        frame['horizon'] = horizon
        forecasts[horizon] = frame
    return forecasts


def _legacy_realised_returns() -> pd.DataFrame:
    price_history = _read_parquet(
        ROOT / 'data' / 'parquet' / 'prices_daily' / 'data.parquet'
    )
    if price_history.empty:
        return pd.DataFrame()
    realised = price_history.rename(
        columns={'ticker': 'security_id', 'date': 'date', 'return': 'return'}
    )
    expected = {'security_id', 'date', 'return'}
    return realised[list(expected)] if expected.issubset(realised) else pd.DataFrame()


def _as_bool(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False)
    return values.fillna(False).astype(str).str.strip().str.lower().isin(
        {'true', '1', 'yes'}
    )


def _integrity_issues(final_portfolio: pd.DataFrame) -> list[ValidationIssue]:
    if final_portfolio.empty:
        return [
            ValidationIssue(
                'data_integrity',
                'error',
                'missing_final_portfolio',
                'No authoritative final_portfolio_weights.csv was available.',
            )
        ]
    issues: list[ValidationIssue] = []
    synthetic = _as_bool(
        final_portfolio.get(
            'is_synthetic_data',
            pd.Series(False, index=final_portfolio.index),
        )
    ) | _as_bool(
        final_portfolio.get(
            'is_synthetic_fundamentals',
            pd.Series(False, index=final_portfolio.index),
        )
    )
    if synthetic.any():
        issues.append(
            ValidationIssue(
                'data_integrity',
                'error',
                'synthetic_investment_inputs',
                'Synthetic metadata or fundamentals are present in the final portfolio.',
                int(synthetic.sum()),
            )
        )
    for column in ('sector', 'country', 'region', 'currency'):
        values = final_portfolio.get(
            column,
            pd.Series('Unknown', index=final_portfolio.index),
        ).fillna('Unknown').astype(str).str.strip().str.lower()
        missing = values.isin({'', 'unknown', 'nan', 'none', 'n/a', '<na>'})
        if missing.any():
            issues.append(
                ValidationIssue(
                    'data_integrity',
                    'error',
                    f'missing_{column}_metadata',
                    f'Selected holdings require observed {column} metadata.',
                    int(missing.sum()),
                )
            )
    prohibited = final_portfolio.get(
        'final_recommendation',
        pd.Series('', index=final_portfolio.index),
    ).fillna('').astype(str).str.contains('avoid|exclude', case=False, regex=True)
    if prohibited.any():
        issues.append(
            ValidationIssue(
                'data_integrity',
                'error',
                'prohibited_selected_recommendation',
                'Avoid or Exclude recommendations were selected into the final portfolio.',
                int(prohibited.sum()),
            )
        )
    return issues


def load_validation_data(
    validation_run_id: str,
    as_of_date: pd.Timestamp,
    output_root: Path | None = None,
) -> ValidationDataPackage:
    outputs = output_root or ROOT / 'reports' / 'outputs'
    walk_forward = outputs / 'walk_forward'
    forecasts, realised, evidence_manifest = _historical_forecasts(walk_forward)
    evidence_mode = str(evidence_manifest.get('evidence_mode', 'current_snapshot'))
    if not forecasts:
        forecasts = _current_forecasts(outputs, as_of_date)
    if realised.empty:
        realised = _legacy_realised_returns()

    historical_portfolio_returns = _read_parquet(
        walk_forward / 'historical_portfolio_returns.parquet'
    )
    historical_risk = _read_parquet(
        walk_forward / 'historical_risk_forecasts.parquet'
    )
    historical_weights = _read_parquet(
        walk_forward / 'historical_portfolio_weights.parquet'
    )
    historical_constraints = _read_parquet(
        walk_forward / 'historical_constraint_report.parquet'
    )
    portfolios = {
        'selected_classical': _read_csv(
            outputs / 'optimised_portfolio_cvar_constrained.csv'
        ),
        'drl': _read_csv(outputs / 'drl_challenger_portfolio.csv'),
        'final_portfolio': _read_csv(outputs / 'final_portfolio_weights.csv'),
        'current_portfolio': _read_csv(outputs / 'current_portfolio_enriched.csv'),
    }
    issues = _integrity_issues(portfolios['final_portfolio'])
    if not forecasts:
        issues.append(
            ValidationIssue(
                'forecasts',
                'warning',
                'missing_forecasts',
                'No forecast snapshots were available.',
            )
        )
    if realised.empty:
        issues.append(
            ValidationIssue(
                'outcomes',
                'warning',
                'missing_realised_returns',
                'No realised return history was available.',
            )
        )
    for position, limitation in enumerate(evidence_manifest.get('limitations', []), start=1):
        issues.append(
            ValidationIssue(
                'chronology',
                'warning',
                f'reconstructed_evidence_limitation_{position}',
                str(limitation),
            )
        )

    regime_history = pd.concat(
        [
            _read_csv(outputs / 'factor_regime_probabilities.csv'),
            _read_csv(outputs / 'chaos_regime_probabilities.csv'),
        ],
        axis=1,
    )
    constraint_reports = {
        'classical': _read_csv(outputs / 'portfolio_constraint_report.csv')
    }
    if not historical_constraints.empty:
        constraint_reports['walk_forward'] = historical_constraints
    return ValidationDataPackage(
        validation_run_id=validation_run_id,
        as_of_date=as_of_date,
        forecasts=forecasts,
        realised_returns=realised,
        risk_forecasts=(
            historical_risk
            if not historical_risk.empty
            else _read_csv(outputs / 'return_distribution_forecasts.csv')
        ),
        portfolio_weights=portfolios,
        portfolio_returns=(
            historical_portfolio_returns
            if not historical_portfolio_returns.empty
            else _read_csv(outputs / 'drl_backtest_results.csv')
        ),
        transaction_costs=(
            historical_portfolio_returns
            if not historical_portfolio_returns.empty
            else _read_csv(outputs / 'drl_trade_list.csv')
        ),
        regime_history=regime_history,
        drl_seed_results=_read_csv(outputs / 'drl_seed_results.csv'),
        drl_benchmark_results=_read_csv(outputs / 'drl_benchmark_comparison.csv'),
        constraint_reports=constraint_reports,
        lineage=_read_csv(outputs / 'model_run_lineage.csv'),
        historical_portfolio_weights=historical_weights,
        evidence_mode=evidence_mode,
        evidence_manifest=evidence_manifest,
        issues=issues,
    )
