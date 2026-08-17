from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.models.supervised_alpha import SupervisedAlphaSettings
from src.utils.config import ROOT, load_yaml


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    temporary.replace(path)


def freeze_supervised_alpha_research(
    *,
    config_path: Path = ROOT / 'configs/ml_forecasting.yaml',
    output_directory: Path | None = None,
    effective_date: str | pd.Timestamp | None = None,
) -> Path:
    raw = load_yaml(config_path).get('supervised_alpha', {})
    settings = SupervisedAlphaSettings.from_mapping(raw, root=ROOT)
    output = Path(output_directory or settings.output_directory)
    decision = pd.Timestamp(
        effective_date or settings.prospective_holdout_start
    ).normalize()
    required = settings.minimum_oos_periods
    horizon = settings.primary_horizon_months
    required_files = {
        'run_manifest': output / 'run_manifest.json',
        'acceptance_decision': output / 'acceptance_decision.csv',
        'ensemble_weights': output / 'ensemble_weights.csv',
        'latest_predictions': output / 'latest_predictions.csv',
        'model_manifest': output / 'model_manifest.csv',
        'model_source': ROOT / 'src/models/supervised_alpha.py',
        'config': config_path,
    }
    missing = [str(path) for path in required_files.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f'Cannot freeze supervised alpha; missing: {missing}')

    model_manifest = pd.read_csv(required_files['model_manifest'])
    bundle_hashes: dict[str, str] = {}
    for row in model_manifest.itertuples(index=False):
        bundle = Path(str(row.model_path))
        if not bundle.is_absolute():
            bundle = ROOT / bundle
        if not bundle.exists():
            raise FileNotFoundError(f'Model bundle is missing: {bundle}')
        actual = _sha256(bundle)
        if actual != str(row.sha256):
            raise RuntimeError(f'Model bundle hash mismatch: {bundle}')
        bundle_hashes[str(int(row.horizon_months))] = actual

    source_hashes = {
        label: _sha256(path)
        for label, path in sorted(required_files.items())
    }
    freeze_payload = {
        'artifact_version': 1,
        'effective_date': decision.date().isoformat(),
        'primary_horizon_months': horizon,
        'required_independent_cohorts': required,
        'first_outcome_due_date': (
            decision + pd.DateOffset(months=horizon)
        ).date().isoformat(),
        'earliest_full_evidence_date': (
            decision + pd.DateOffset(months=horizon * required)
        ).date().isoformat(),
        'source_hashes': source_hashes,
        'model_bundle_hashes': bundle_hashes,
        'legacy_oos_eligible_for_deployment': False,
        'prospective_evidence_only': True,
    }
    freeze_hash = hashlib.sha256(
        json.dumps(freeze_payload, sort_keys=True).encode('utf-8')
    ).hexdigest()
    payload = {
        **freeze_payload,
        'freeze_hash': freeze_hash,
        'frozen_at': datetime.now(UTC).isoformat(),
    }
    path = output / 'prospective_freeze_manifest.json'
    if path.exists():
        existing = json.loads(path.read_text(encoding='utf-8'))
        if existing.get('freeze_hash') != freeze_hash:
            raise RuntimeError(
                'A different supervised-alpha version is already frozen. '
                'Create a versioned research directory instead of overwriting it.'
            )
        return path
    _atomic_json(path, payload)
    return path
