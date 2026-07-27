from __future__ import annotations

import argparse
from datetime import datetime
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.production.orchestrator import run_production_pipeline
from src.utils.config import load_settings


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Wolf Quant Model production operations pipeline.")
    parser.add_argument("--mode", choices=["daily", "weekly", "monthly", "release_candidate"], default="daily")
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--backend", choices=["legacy_csv", "duckdb", "shadow"], default=None)
    parser.add_argument("--force-stale-lock-recovery", action="store_true", default=True)
    parser.add_argument("--no-force-stale-lock-recovery", action="store_false", dest="force_stale_lock_recovery")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    arguments = parse_arguments()
    settings = load_settings()
    as_of_date = datetime.fromisoformat(arguments.as_of_date) if arguments.as_of_date else None
    if arguments.dry_run:
        print("Dry run: production configuration loaded successfully.")
        print(f"Mode: {arguments.mode}")
        print(f"Backend override: {arguments.backend}")
        return 0
    result = run_production_pipeline(
        settings=settings,
        mode=arguments.mode,
        as_of_date=as_of_date,
        backend_override=arguments.backend,
        force_stale_lock_recovery=arguments.force_stale_lock_recovery,
    )
    print(f"Production run: {result.production_run_id}")
    print(f"Status: {result.status}")
    print(f"Approval: {result.approval_status}")
    print(f"Output: {result.output_directory}")
    if result.status == "FAILED":
        return 3
    if result.status == "BLOCKED":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
