from __future__ import annotations

import argparse
from datetime import UTC, datetime
import logging
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DuckDBRepository
from src.production.shadow_operation import (
    evaluate_pending_shadow_cycles,
    run_shadow_operation_from_outputs,
    write_shadow_report,
)
from src.utils.config import ROOT, load_yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record and evaluate immutable monthly model shadow cycles."
    )
    parser.add_argument("--as-of", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--production-run-id", default=None)
    parser.add_argument("--governance-status", default="CONDITIONALLY_APPROVED")
    parser.add_argument("--evaluate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    as_of = pd.Timestamp(args.as_of)
    if args.evaluate_only:
        shadow_config = (
            load_yaml("configs/production.yaml")
            .get("production", {})
            .get("shadow_operation", {})
        )
        repository = DuckDBRepository(load_data_config().duckdb_path)
        repository.execute_migrations(ROOT / "sql" / "migrations")
        completed = evaluate_pending_shadow_cycles(
            repository,
            evaluation_as_of=as_of,
        )
        write_shadow_report(
            repository,
            ROOT / "reports" / "outputs" / "shadow_operation",
            required_cycles=int(
                shadow_config.get("required_prospective_cycles", 3)
            ),
            prospective_start_date=shadow_config.get(
                "prospective_start_date"
            ),
        )
        logging.info("Evaluated %s completed shadow cycles.", completed)
        return 0
    cycle_id = run_shadow_operation_from_outputs(
        as_of_date=as_of,
        production_run_id=args.production_run_id,
        governance_status=args.governance_status,
    )
    logging.info("Recorded immutable shadow cycle %s.", cycle_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
