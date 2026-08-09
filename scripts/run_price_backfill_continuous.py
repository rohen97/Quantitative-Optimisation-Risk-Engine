from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DuckDBRepository

DEFAULT_REGIONS = ("US", "UK", "DACH", "Mainland China", "Hong Kong", "EU ex-DACH")
DEFAULT_STATUSES = ("Active",)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Continuously run resumable price backfill passes until complete.")
    parser.add_argument("--regions", nargs="*", default=list(DEFAULT_REGIONS))
    parser.add_argument("--listing-status", nargs="*", default=list(DEFAULT_STATUSES))
    parser.add_argument("--providers", default="yfinance", help="Comma-separated DATA_PRICE_PROVIDERS for child passes.")
    parser.add_argument("--max-symbols", type=int, default=240)
    parser.add_argument("--batch-size", type=int, default=80)
    parser.add_argument("--sleep-seconds", type=float, default=0.02)
    parser.add_argument("--pause-between-passes", type=float, default=5.0)
    parser.add_argument("--max-passes", type=int, default=0, help="0 means run until complete.")
    parser.add_argument("--max-consecutive-empty", type=int, default=3)
    parser.add_argument("--include-delisted", action="store_true")
    parser.add_argument("--run-migrations-first", action="store_true")
    parser.add_argument("--refresh-missing-volume", action="store_true")
    parser.add_argument("--minimum-volume-rows", type=int, default=20)
    return parser.parse_args()


def sql_list(values: list[str]) -> str:
    return ", ".join("'" + value.replace("'", "''") + "'" for value in values)


def progress(
    regions: list[str],
    statuses: list[str],
    refresh_missing_volume: bool = False,
    minimum_volume_rows: int = 20,
) -> tuple[int, int, str]:
    data_config = load_data_config()
    repo = DuckDBRepository(data_config.duckdb_path)
    if refresh_missing_volume:
        coverage_cte = """
        SELECT security_id
        FROM prices_daily
        GROUP BY security_id
        HAVING COUNT(*) FILTER (WHERE volume IS NOT NULL AND volume > 0) >= ?
        """
        parameters = [int(minimum_volume_rows)]
    else:
        coverage_cte = "SELECT DISTINCT security_id FROM prices_daily"
        parameters = []
    frame = repo.query(
        f"""
        WITH covered AS (
            {coverage_cte}
        )
        SELECT s.region,
               count(DISTINCT s.security_id) AS universe,
               count(DISTINCT p.security_id) AS priced,
               count(DISTINCT s.security_id) - count(DISTINCT p.security_id) AS remaining
        FROM securities s
        LEFT JOIN covered p USING (security_id)
        WHERE s.region IN ({sql_list(regions)})
          AND s.listing_status IN ({sql_list(statuses)})
          AND s.instrument_type = 'Equity'
        GROUP BY 1
        ORDER BY 1
        """,
        parameters,
    )
    repo.close()
    remaining = int(frame["remaining"].sum()) if not frame.empty else 0
    priced = int(frame["priced"].sum()) if not frame.empty else 0
    return priced, remaining, frame.to_string(index=False)


def run_pass(args: argparse.Namespace, pass_number: int) -> int:
    command = [
        sys.executable,
        "scripts/run_price_backfill.py",
        "--max-symbols",
        str(args.max_symbols),
        "--batch-size",
        str(args.batch_size),
        "--sleep-seconds",
        str(args.sleep_seconds),
    ]
    if pass_number > 1 or not args.run_migrations_first:
        command.append("--skip-migrations")
    if args.regions:
        command.extend(["--regions", *args.regions])
    if args.listing_status:
        command.extend(["--listing-status", *args.listing_status])
    if args.include_delisted:
        command.append("--include-delisted")
    if args.refresh_missing_volume:
        command.extend(["--refresh-missing-volume", "--minimum-volume-rows", str(args.minimum_volume_rows)])

    env = os.environ.copy()
    env["DATA_PRICE_PROVIDERS"] = args.providers
    logging.info("Starting pass %s: %s", pass_number, " ".join(command))
    completed = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], env=env, check=False)
    logging.info("Pass %s exited with code %s", pass_number, completed.returncode)
    return int(completed.returncode)


def main() -> int:
    args = parse_args()
    if args.include_delisted and "Delisted" not in args.listing_status:
        args.listing_status.append("Delisted")
    log_path = Path("logs/price_backfill_continuous.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_path, encoding="utf-8")],
    )

    empty_passes = 0
    pass_number = 0
    while True:
        pass_number += 1
        before_priced, before_remaining, before_table = progress(
            args.regions,
            args.listing_status,
            args.refresh_missing_volume,
            args.minimum_volume_rows,
        )
        logging.info("Before pass %s: priced=%s remaining=%s\n%s", pass_number, before_priced, before_remaining, before_table)
        if before_remaining <= 0:
            logging.info("Backfill complete for requested universe.")
            return 0
        if args.max_passes and pass_number > args.max_passes:
            logging.info("Reached max passes: %s", args.max_passes)
            return 0

        return_code = run_pass(args, pass_number)
        after_priced, after_remaining, after_table = progress(
            args.regions,
            args.listing_status,
            args.refresh_missing_volume,
            args.minimum_volume_rows,
        )
        logging.info("After pass %s: priced=%s remaining=%s\n%s", pass_number, after_priced, after_remaining, after_table)
        if after_priced <= before_priced:
            empty_passes += 1
            logging.warning("Pass %s did not increase priced security count. consecutive_empty=%s", pass_number, empty_passes)
        else:
            empty_passes = 0
        if empty_passes >= args.max_consecutive_empty:
            logging.error("Stopping after %s consecutive passes without new priced securities.", empty_passes)
            return 2
        if return_code != 0:
            logging.warning("Continuing after non-zero pass return code %s because data may have partially committed.", return_code)
        if args.pause_between_passes > 0:
            time.sleep(args.pause_between_passes)


if __name__ == "__main__":
    raise SystemExit(main())
