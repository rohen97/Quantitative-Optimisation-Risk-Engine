from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.reporting.ic_pipeline import run_ic_reporting
from src.utils.config import load_settings


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the Wolf Investment Committee reporting package."
    )
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--model-run-id", default=None)
    parser.add_argument(
        "--backend",
        choices=["legacy_csv", "duckdb", "shadow"],
        default=None,
    )
    parser.add_argument("--skip-pdf", action="store_true")
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    arguments = parse_arguments()
    result = run_ic_reporting(
        settings=load_settings(),
        as_of_date=arguments.as_of_date,
        model_run_id=arguments.model_run_id,
        backend_override=arguments.backend,
        generate_pdf=not arguments.skip_pdf,
        strict=arguments.strict,
        output_root=arguments.output_root,
    )
    print(f"IC report generated: {result.html_path}")
    print(f"Readiness status: {result.readiness_status}")


if __name__ == "__main__":
    main()
