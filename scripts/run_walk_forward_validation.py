from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.validation.validation_pipeline import run_validation_pipeline
from src.validation.snapshot_archive import archive_walk_forward_snapshots
from src.validation.walk_forward import load_walk_forward_config, run_walk_forward


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Build reconstructed point-in-time evidence and run model validation.'
    )
    parser.add_argument('--output-directory', default=None)
    parser.add_argument('--start-date', default=None)
    parser.add_argument('--forecast-end-date', default=None)
    parser.add_argument('--strategy-end-date', default=None)
    parser.add_argument('--filing-lag-days', type=int, default=None)
    parser.add_argument('--minimum-annual-periods', type=int, default=None)
    parser.add_argument('--minimum-training-price-rows', type=int, default=None)
    parser.add_argument('--price-lookback-rows', type=int, default=None)
    parser.add_argument('--skip-validation', action='store_true')
    parser.add_argument(
        '--validation-mode',
        choices=['smoke', 'standard', 'full', 'release_candidate'],
        default='full',
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s - %(message)s',
    )
    args = parse_args()
    config = load_walk_forward_config(
        output_directory=args.output_directory,
        start_date=args.start_date,
        forecast_end_date=args.forecast_end_date,
        strategy_end_date=args.strategy_end_date,
        filing_lag_days=args.filing_lag_days,
        minimum_annual_periods=args.minimum_annual_periods,
        minimum_training_price_rows=args.minimum_training_price_rows,
        price_lookback_rows=args.price_lookback_rows,
    )
    result = run_walk_forward(config)
    archive = archive_walk_forward_snapshots(result.output_directory)
    print(f'Walk-forward output: {result.output_directory}')
    print(f'Forecast rows: {result.forecast_rows}')
    print(f'Aligned outcomes: {result.outcome_rows}')
    print(f'Portfolio months: {result.portfolio_months}')
    print(f'Risk observations: {result.risk_observations}')
    print(f'Evidence mode: {result.evidence_mode}')
    print(f'Archived decision snapshots: {archive.manifests}')
    if args.skip_validation:
        return
    validation = run_validation_pipeline(
        execution_mode=args.validation_mode,
        backend_override='duckdb',
        run_sensitivity=True,
        run_ablation=True,
    )
    print(f'Validation status: {validation.approval_status}')
    print(f'Validation score: {validation.overall_score:.1f}')
    print(f'Validation output: {validation.output_directory}')


if __name__ == '__main__':
    main()
