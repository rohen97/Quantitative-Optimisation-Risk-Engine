from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from src.production.supervised_alpha_shadow import freeze_supervised_alpha_research


def test_supervised_alpha_freeze_is_immutable(tmp_path: Path, monkeypatch):
    monkeypatch.setattr('src.production.supervised_alpha_shadow.ROOT', tmp_path)
    output = tmp_path / 'outputs'
    output.mkdir()
    config = tmp_path / 'ml.yaml'
    config.write_text(
        """supervised_alpha:
  primary_horizon_months: 3
  validation:
    prospective_holdout_start: 2026-08-31
  acceptance:
    minimum_oos_periods: 12
""",
        encoding='utf-8',
    )
    for name in (
        'run_manifest.json',
        'acceptance_decision.csv',
        'ensemble_weights.csv',
        'latest_predictions.csv',
    ):
        (output / name).write_text('evidence\n', encoding='utf-8')
    bundle = tmp_path / 'model.joblib'
    bundle.write_bytes(b'observed-model-bundle')
    model_source = tmp_path / 'src' / 'models' / 'supervised_alpha.py'
    model_source.parent.mkdir(parents=True)
    model_source.write_text('# frozen model source\n', encoding='utf-8')
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    pd.DataFrame(
        [
            {
                'horizon_months': 3,
                'model_path': bundle.relative_to(tmp_path).as_posix(),
                'sha256': digest,
            }
        ]
    ).to_csv(output / 'model_manifest.csv', index=False)

    first = freeze_supervised_alpha_research(
        config_path=config,
        output_directory=output,
    )
    second = freeze_supervised_alpha_research(
        config_path=config,
        output_directory=output,
    )
    payload = json.loads(first.read_text(encoding='utf-8'))
    assert first == second
    assert payload['required_independent_cohorts'] == 12
    assert payload['earliest_full_evidence_date'] == '2029-08-31'

    (output / 'latest_predictions.csv').write_text('changed\n', encoding='utf-8')
    with pytest.raises(RuntimeError, match='already frozen'):
        freeze_supervised_alpha_research(
            config_path=config,
            output_directory=output,
        )
