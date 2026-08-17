from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.supervised_alpha import (
    ARTIFACT_VERSION,
    SupervisedAlphaSettings,
    _atomic_checkpoint_frame,
    _checkpoint_paths,
    _validation_checkpoint_signature,
    build_candidate_specs,
    build_supervised_alpha_dataset,
    evaluate_predictions,
)
from src.utils.config import ROOT, load_yaml


LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Recompute validation metrics from frozen model predictions after a selection-policy change.'
    )
    parser.add_argument(
        '--features',
        default='reports/outputs/walk_forward/historical_features.parquet',
    )
    parser.add_argument(
        '--outcomes',
        default='reports/outputs/walk_forward/historical_realised_outcomes_extended.parquet',
    )
    parser.add_argument('--config', default='configs/ml_forecasting.yaml')
    parser.add_argument(
        '--drop-retired-candidates',
        action='store_true',
        help='Drop checkpoint rows for candidates no longer present in the configured grid.',
    )
    return parser.parse_args()


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def main() -> None:
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    args = parse_args()
    settings = SupervisedAlphaSettings.from_mapping(
        load_yaml(args.config).get('supervised_alpha', {}),
        root=ROOT,
    )
    dataset, _, _ = build_supervised_alpha_dataset(
        pd.read_parquet(_resolve(args.features)),
        pd.read_parquet(_resolve(args.outcomes)),
        settings,
    )
    specs = build_candidate_specs(settings)
    expected_candidates = {spec.key: spec for spec in specs}

    for horizon in settings.horizons_months:
        horizon_data = dataset.loc[dataset['horizon_months'].eq(horizon)].copy()
        valid_row_ids = set(horizon_data['row_id'].astype(str))
        paths = _checkpoint_paths(settings.checkpoint_directory, horizon)
        predictions = pd.read_parquet(paths['predictions'])
        predictions['row_id'] = predictions['row_id'].astype(str)
        predictions['target_date'] = pd.to_datetime(
            predictions['target_date'], errors='coerce'
        )
        original_rows = len(predictions)
        predictions = predictions.loc[
            predictions['target_date'].lt(settings.frozen_test_start)
        ].copy()
        embargoed_rows = original_rows - len(predictions)
        before_coverage_gate = len(predictions)
        predictions = predictions.loc[
            predictions['row_id'].isin(valid_row_ids)
        ].copy()
        incomplete_cross_section_rows = before_coverage_gate - len(predictions)
        if predictions.empty:
            raise RuntimeError(
                f'{horizon}m checkpoint has no valid validation predictions before the frozen OOS start.'
            )
        unknown = set(predictions['candidate']) - set(expected_candidates)
        if unknown:
            if not args.drop_retired_candidates:
                raise RuntimeError(
                    f'{horizon}m checkpoint contains retired candidates: {sorted(unknown)}; '
                    'rerun with --drop-retired-candidates after reviewing the config change.'
                )
            LOGGER.info(
                'Dropping retired %sm candidates: %s.',
                horizon,
                sorted(unknown),
            )
            predictions = predictions.loc[
                predictions['candidate'].isin(expected_candidates)
            ].copy()
        summary_rows = []
        monthly_frames = []
        expected_folds = int(predictions['fold'].nunique())
        for candidate, candidate_predictions in predictions.groupby('candidate', sort=True):
            metrics, monthly = evaluate_predictions(
                candidate_predictions,
                settings,
                horizon_months=horizon,
            )
            spec = expected_candidates[candidate]
            fold_count = int(candidate_predictions['fold'].nunique())
            summary_rows.append(
                {
                    'horizon_months': horizon,
                    'candidate': candidate,
                    'family': spec.family,
                    'category': spec.category,
                    'folds': fold_count,
                    'expected_folds': expected_folds,
                    'complete_validation': fold_count == expected_folds,
                    **metrics,
                }
            )
            monthly['candidate'] = candidate
            monthly['family'] = spec.family
            monthly['split'] = 'validation'
            monthly_frames.append(monthly)
        _atomic_checkpoint_frame(pd.DataFrame(summary_rows), paths['summary'])
        _atomic_checkpoint_frame(pd.concat(monthly_frames, ignore_index=True), paths['monthly'])
        kept_folds = set(predictions['fold'].astype(str))
        screening = pd.read_parquet(paths['screening'])
        failures = pd.read_parquet(paths['failures'])
        if 'fold' in screening:
            screening = screening.loc[screening['fold'].astype(str).isin(kept_folds)].copy()
        if 'fold' in failures:
            failures = failures.loc[failures['fold'].astype(str).isin(kept_folds)].copy()
        if 'candidate' in failures:
            failures = failures.loc[
                failures['candidate'].astype(str).isin(expected_candidates)
            ].copy()
        _atomic_checkpoint_frame(screening, paths['screening'])
        _atomic_checkpoint_frame(failures, paths['failures'])
        _atomic_checkpoint_frame(predictions, paths['predictions'])
        metadata = json.loads(paths['metadata'].read_text(encoding='utf-8'))
        metadata.update(
            {
                'artifact_version': ARTIFACT_VERSION,
                'signature': _validation_checkpoint_signature(
                    horizon_data,
                    settings,
                    specs,
                    horizon,
                ),
                'metrics_recomputed_from_frozen_predictions': True,
                'selection_policy': 'rank_normalised_cost_aware_retention',
                'validation_labels_mature_before': str(settings.frozen_test_start.date()),
            }
        )
        temporary = paths['metadata'].with_suffix('.json.tmp')
        temporary.write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + '\n',
            encoding='utf-8',
        )
        temporary.replace(paths['metadata'])
        LOGGER.info(
            'Recomputed %sm validation metrics from %s frozen candidate predictions.',
            horizon,
            len(predictions),
        )
        LOGGER.info(
            'Dropped %s %sm validation predictions whose labels mature inside the legacy OOS calendar.',
            embargoed_rows,
            horizon,
        )
        LOGGER.info(
            'Dropped %s %sm validation predictions from incomplete outcome cross-sections.',
            incomplete_cross_section_rows,
            horizon,
        )


if __name__ == '__main__':
    main()
