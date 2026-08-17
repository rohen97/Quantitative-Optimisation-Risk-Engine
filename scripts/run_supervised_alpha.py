from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path
import sys

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.regional_alpha import RegionalAlphaSettings, add_regional_alpha_signals
from src.data.lineage import get_git_metadata
from src.models.supervised_alpha import (
    SupervisedAlphaSettings,
    apply_governed_supervised_alpha_overlay,
    run_supervised_alpha_research,
)
from src.optimisation.optimisers import regional_alpha_portfolio
from src.reporting.supervised_alpha import (
    load_supervised_alpha_artifacts,
    write_supervised_alpha_artifacts,
)
from src.utils.config import ROOT, load_yaml
from src.validation.walk_forward import (
    build_walk_forward_feature_panel,
    build_walk_forward_outcome_panel,
    load_walk_forward_config,
)


LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Train and freeze-test supervised benchmark-relative equity alpha challengers.'
    )
    parser.add_argument('--config', default='configs/ml_forecasting.yaml')
    parser.add_argument(
        '--feature-panel',
        default='reports/outputs/walk_forward/historical_features.parquet',
    )
    parser.add_argument(
        '--outcomes',
        default='reports/outputs/walk_forward/historical_realised_outcomes_extended.parquet',
    )
    parser.add_argument(
        '--latest-features',
        default='reports/outputs/optimiser_input_dataset.csv',
    )
    parser.add_argument('--output-directory', default=None)
    parser.add_argument('--force-feature-panel', action='store_true')
    parser.add_argument('--force-outcomes', action='store_true')
    parser.add_argument('--seal-existing', action='store_true')
    parser.add_argument('--horizons', nargs='+', type=int, default=None)
    parser.add_argument('--families', nargs='+', default=None)
    return parser.parse_args()


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _load_latest(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == '.parquet':
        return pd.read_parquet(path)
    return pd.read_csv(path, low_memory=False)


def _source_artifacts(
    feature_path: Path,
    outcomes_path: Path,
    latest_path: Path,
    config_path: Path,
) -> dict[str, object]:
    artifacts: dict[str, object] = {}
    for label, path in (
        ('feature_panel', feature_path),
        ('outcomes', outcomes_path),
        ('latest_features', latest_path),
        ('config', config_path),
        ('model_source', ROOT / 'src/models/supervised_alpha.py'),
    ):
        artifacts[label] = _repo_relative(path)
        artifacts[f'{label}_sha256'] = _sha256(path) if path.exists() else None
    return artifacts


def _require_xgboost(settings: SupervisedAlphaSettings) -> None:
    if not {'xgboost', 'xgb_ranker'}.intersection(settings.enabled_families):
        return
    try:
        import xgboost  # noqa: F401
    except ImportError as error:
        raise RuntimeError(
            'XGBoost challengers are enabled but xgboost is absent. Install with '
            '`python -m pip install -e ".[ml]"`.'
        ) from error


def _write_governed_portfolio(
    latest: pd.DataFrame,
    result,
    settings: SupervisedAlphaSettings,
) -> None:
    governed = apply_governed_supervised_alpha_overlay(
        latest,
        result.latest_predictions,
        result.acceptance_decision,
        settings,
    )
    optimisation = load_yaml('configs/optimisation.yaml').get('optimisation', {})
    method = optimisation.get('methods', {}).get('regional_alpha', {})
    constraints = {
        **optimisation.get('constraints', {}),
        'maximum_candidates': int(optimisation.get('maximum_candidates', 2000)),
        'allow_synthetic_data': str(optimisation.get('mode', '')).lower() == 'mock',
    }
    regional_settings = RegionalAlphaSettings.from_mapping(
        method,
        portfolio_nav_usd=settings.portfolio_nav_usd,
    )
    enriched = add_regional_alpha_signals(governed, regional_settings)
    portfolio = regional_alpha_portfolio(enriched, constraints)
    output = settings.output_directory
    output.mkdir(parents=True, exist_ok=True)
    governed.to_csv(output / 'governed_optimiser_input.csv', index=False)
    portfolio.to_csv(output / 'optimised_portfolio_supervised_alpha.csv', index=False)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    args = parse_args()
    raw = load_yaml(args.config).get('supervised_alpha', {})
    overrides = dict(raw)
    if args.output_directory:
        overrides['output_directory'] = args.output_directory
    if args.horizons:
        overrides['horizons_months'] = args.horizons
    if args.families:
        models = dict(overrides.get('models', {}))
        models['enabled_families'] = args.families
        overrides['models'] = models
    settings = SupervisedAlphaSettings.from_mapping(overrides, root=ROOT)
    _require_xgboost(settings)

    feature_path = _resolve(args.feature_panel)
    outcomes_path = _resolve(args.outcomes)
    latest_path = _resolve(args.latest_features)
    config_path = _resolve(args.config)
    if args.seal_existing:
        result = load_supervised_alpha_artifacts(settings.output_directory)
        latest = _load_latest(latest_path)
        source_artifacts = _source_artifacts(
            feature_path,
            outcomes_path,
            latest_path,
            config_path,
        )
        manifest_path = settings.output_directory / 'run_manifest.json'
        if manifest_path.exists():
            try:
                previous = json.loads(manifest_path.read_text(encoding='utf-8'))
                source_artifacts = {
                    **dict(previous.get('source_artifacts', {})),
                    **source_artifacts,
                }
            except (OSError, json.JSONDecodeError):
                LOGGER.warning('Could not preserve the prior supervised-alpha manifest.')
        git_commit, git_dirty = get_git_metadata(ROOT)
        source_artifacts.update(
            {
                'git_commit_at_reseal': git_commit,
                'git_dirty_at_reseal': git_dirty,
                'resealed_existing_artifacts': True,
            }
        )
        _write_governed_portfolio(latest, result, settings)
        write_supervised_alpha_artifacts(
            result,
            settings,
            source_artifacts=source_artifacts,
        )
        LOGGER.info('Existing supervised-alpha artifacts resealed at %s.', settings.output_directory)
        return
    if args.force_feature_panel or not feature_path.exists():
        walk_forward = load_walk_forward_config()
        feature_panel = build_walk_forward_feature_panel(
            walk_forward,
            output_path=feature_path,
            force=args.force_feature_panel,
        )
    else:
        feature_panel = pd.read_parquet(feature_path)
    if args.force_outcomes or not outcomes_path.exists():
        outcomes = build_walk_forward_outcome_panel(
            feature_panel,
            load_walk_forward_config(),
            output_path=outcomes_path,
            force=args.force_outcomes,
        )
    else:
        outcomes = pd.read_parquet(outcomes_path)
    latest = _load_latest(latest_path)
    LOGGER.info(
        'Starting supervised-alpha research: feature_rows=%s outcomes=%s latest=%s horizons=%s.',
        len(feature_panel),
        len(outcomes),
        len(latest),
        settings.horizons_months,
    )
    result = run_supervised_alpha_research(
        feature_panel,
        outcomes,
        latest,
        settings,
    )
    git_commit, git_dirty = get_git_metadata(ROOT)
    source_artifacts = _source_artifacts(
        feature_path,
        outcomes_path,
        latest_path,
        config_path,
    )
    source_artifacts.update(
        {
            'git_commit_at_training': git_commit,
            'git_dirty_at_training': git_dirty,
        }
    )
    _write_governed_portfolio(latest, result, settings)
    write_supervised_alpha_artifacts(
        result,
        settings,
        source_artifacts=source_artifacts,
    )
    overall = result.acceptance_decision.loc[
        result.acceptance_decision['scope'].eq('overall')
    ].iloc[0]
    LOGGER.info(
        'Supervised-alpha research complete: status=%s blend=%.3f outputs=%s failures=%s.',
        overall['status'],
        float(overall['deployment_blend_weight']),
        settings.output_directory,
        len(result.failures),
    )


if __name__ == '__main__':
    main()
