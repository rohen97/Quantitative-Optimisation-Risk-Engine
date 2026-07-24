from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.config import load_settings
from src.validation.validation_pipeline import run_validation_pipeline


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run end-to-end validation for The Wolf Quant Model.")
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--model-run-id", default=None)
    parser.add_argument("--backend", choices=["legacy_csv", "duckdb", "shadow"], default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--skip-sensitivity", action="store_true")
    parser.add_argument("--skip-ablation", action="store_true")
    parser.add_argument("--bootstrap-samples", type=int, default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--mode", choices=["smoke", "standard", "full", "release_candidate"], default=None)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    arguments = parse_arguments()
    result = run_validation_pipeline(
        settings=load_settings(),
        as_of_date=arguments.as_of_date,
        model_run_id=arguments.model_run_id,
        backend_override=arguments.backend,
        strict=arguments.strict,
        run_sensitivity=not arguments.skip_sensitivity,
        run_ablation=not arguments.skip_ablation,
        bootstrap_samples_override=arguments.bootstrap_samples,
        output_root=arguments.output_root,
        execution_mode=arguments.mode,
    )
    print(f"Validation run: {result.validation_run_id}")
    print(f"Approval status: {result.approval_status}")
    print(f"Overall score: {result.overall_score:.1f}")
    print(f"Output directory: {result.output_directory}")


if __name__ == "__main__":
    main()
