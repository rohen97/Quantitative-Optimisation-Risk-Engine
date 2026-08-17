from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

import numpy as np
import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.supervised_alpha import (
    SupervisedAlphaSettings,
    _checkpoint_paths,
    _validation_checkpoint_signature,
    build_candidate_specs,
    build_supervised_alpha_dataset,
)
from src.utils.config import ROOT, load_yaml


LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Rekey validation checkpoints after a strictly OOS-only outcome extension.'
    )
    parser.add_argument(
        '--features',
        default='reports/outputs/walk_forward/historical_features.parquet',
    )
    parser.add_argument(
        '--previous-outcomes',
        default='reports/outputs/walk_forward/historical_realised_outcomes.parquet',
    )
    parser.add_argument(
        '--extended-outcomes',
        default='reports/outputs/walk_forward/historical_realised_outcomes_extended.parquet',
    )
    parser.add_argument('--config', default='configs/ml_forecasting.yaml')
    return parser.parse_args()


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def _validation_contract(data: pd.DataFrame, end_date: pd.Timestamp) -> pd.DataFrame:
    columns = ['row_id', 'target_date', 'target_excess_return', 'realised_return']
    return (
        data.loc[data['as_of_date'].le(end_date), columns]
        .sort_values('row_id')
        .reset_index(drop=True)
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    args = parse_args()
    settings = SupervisedAlphaSettings.from_mapping(
        load_yaml(args.config).get('supervised_alpha', {}),
        root=ROOT,
    )
    features = pd.read_parquet(_resolve(args.features))
    previous, _, _ = build_supervised_alpha_dataset(
        features,
        pd.read_parquet(_resolve(args.previous_outcomes)),
        settings,
    )
    extended, _, _ = build_supervised_alpha_dataset(
        features,
        pd.read_parquet(_resolve(args.extended_outcomes)),
        settings,
    )
    specs = build_candidate_specs(settings)

    for horizon in settings.horizons_months:
        old_horizon = previous.loc[previous['horizon_months'].eq(horizon)].copy()
        new_horizon = extended.loc[extended['horizon_months'].eq(horizon)].copy()
        paths = _checkpoint_paths(settings.checkpoint_directory, horizon)
        metadata = json.loads(paths['metadata'].read_text(encoding='utf-8'))
        old_signature = _validation_checkpoint_signature(
            old_horizon,
            settings,
            specs,
            horizon,
        )
        if metadata.get('signature') != old_signature:
            raise RuntimeError(
                f'{horizon}m checkpoint does not match the current code, settings, and previous evidence.'
            )
        old_contract = _validation_contract(old_horizon, settings.validation_end)
        new_contract = _validation_contract(new_horizon, settings.validation_end)
        if not old_contract['row_id'].equals(new_contract['row_id']):
            raise RuntimeError(f'{horizon}m validation row identities changed.')
        if not old_contract['target_date'].equals(new_contract['target_date']):
            raise RuntimeError(f'{horizon}m validation target dates changed.')
        for column in ('target_excess_return', 'realised_return'):
            if not np.allclose(
                old_contract[column].to_numpy(dtype=float),
                new_contract[column].to_numpy(dtype=float),
                equal_nan=True,
                rtol=0.0,
                atol=1e-12,
            ):
                raise RuntimeError(f'{horizon}m validation values changed in {column}.')
        checkpoint_predictions = pd.read_parquet(paths['predictions'])
        if pd.to_datetime(checkpoint_predictions['as_of_date']).max() > settings.validation_end:
            raise RuntimeError(f'{horizon}m checkpoint contains post-validation predictions.')
        metadata['signature'] = _validation_checkpoint_signature(
            new_horizon,
            settings,
            specs,
            horizon,
        )
        metadata['rekey_basis'] = 'strictly_oos_only_outcome_extension'
        metadata['validation_rows_verified'] = len(new_contract)
        temporary = paths['metadata'].with_suffix('.json.tmp')
        temporary.write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + '\n',
            encoding='utf-8',
        )
        temporary.replace(paths['metadata'])
        LOGGER.info(
            'Rekeyed %sm checkpoint after verifying %s unchanged validation rows.',
            horizon,
            len(new_contract),
        )


if __name__ == '__main__':
    main()
