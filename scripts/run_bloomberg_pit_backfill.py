from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date
import hashlib
import json
import logging
from pathlib import Path
import sys
import time
from uuid import uuid4

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_bloomberg_backfill import load_candidates
from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DuckDBRepository
from src.data.schemas import SCHEMAS
from src.data_ingestion.bloomberg_adapter import BloombergConfig, BloombergDesktopAdapter
from src.data_ingestion.bloomberg_pit import (
    CORPORATE_ACTION_FIELDS,
    CURRENCY_FIELDS,
    FUNDAMENTAL_FIELDS,
    IDENTIFIER_FIELDS,
    MARKET_CAP_FIELDS,
    normalise_corporate_actions,
    normalise_fundamental_snapshot,
    normalise_identifier_snapshot,
    normalise_market_cap_history,
    reference_currency_map,
    to_model_fundamentals,
)


LOGGER = logging.getLogger(__name__)
DEFAULT_REGIONS = ("Mainland China", "Hong Kong")
ALL_DATASETS = ("identifiers", "corporate-actions", "market-cap", "fundamentals")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build immutable Bloomberg point-in-time evidence in DuckDB."
    )
    parser.add_argument("--regions", nargs="*", default=list(DEFAULT_REGIONS))
    parser.add_argument("--listing-status", nargs="*", default=["Active"])
    parser.add_argument("--symbols", nargs="*", default=[])
    parser.add_argument(
        "--universe-file",
        type=Path,
        default=None,
        help="Optional CSV/Parquet/TXT containing security_id values to scope a quota-efficient run.",
    )
    parser.add_argument("--start", default="2018-07-01")
    parser.add_argument("--end", default=date.today().isoformat())
    parser.add_argument("--datasets", nargs="*", choices=ALL_DATASETS, default=list(ALL_DATASETS))
    parser.add_argument("--period-types", nargs="*", choices=("Q", "Y"), default=["Q", "Y"])
    parser.add_argument("--snapshot-dates", nargs="*", default=[])
    parser.add_argument("--request-size", type=int, default=100)
    parser.add_argument("--max-symbols", type=int, default=0)
    parser.add_argument("--max-snapshots", type=int, default=0)
    parser.add_argument("--sleep-seconds", type=float, default=0.05)
    parser.add_argument("--include-delisted", action="store_true")
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--skip-migrations", action="store_true")
    parser.add_argument("--coverage-only", action="store_true")
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path("data/locks/bloomberg_pit_checkpoint.json"),
    )
    parser.add_argument(
        "--coverage-report",
        type=Path,
        default=Path("reports/outputs/bloomberg_pit_coverage.csv"),
    )
    return parser.parse_args()


class Checkpoint:
    def __init__(self, path: Path, enabled: bool) -> None:
        self.path = path
        self.enabled = enabled
        self.completed: set[str] = set()
        if enabled and path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.completed = set(map(str, payload.get("completed", [])))
            except (OSError, json.JSONDecodeError):
                LOGGER.warning("Ignoring unreadable Bloomberg PIT checkpoint %s.", path)

    def contains(self, key: str) -> bool:
        return self.enabled and key in self.completed

    def mark(self, key: str) -> None:
        if not self.enabled:
            return
        self.completed.add(key)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps({"completed": sorted(self.completed)}, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)


def _candidate_hash(candidates: pd.DataFrame) -> str:
    values = candidates[["security_id", "provider_symbol"]].astype(str).agg("|".join, axis=1)
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()[:16]


def _snapshot_dates(args: argparse.Namespace) -> list[pd.Timestamp]:
    start = pd.Timestamp(args.start).normalize()
    end = pd.Timestamp(args.end).normalize()
    if start > end:
        raise ValueError("--start must not be after --end")
    if args.snapshot_dates:
        dates = sorted({pd.Timestamp(value).normalize() for value in args.snapshot_dates})
        dates = [value for value in dates if start <= value <= end]
    else:
        dates = list(pd.date_range(start, end, freq="ME"))
    if args.max_snapshots > 0:
        dates = dates[: args.max_snapshots]
    return dates


def _load_universe_ids(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Bloomberg PIT universe file does not exist: {path}")
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        frame = pd.read_parquet(path)
    elif suffix == ".csv":
        frame = pd.read_csv(path, dtype=str)
    else:
        values = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
        return sorted({value for value in values if value})
    column = next((name for name in ("security_id", "ticker") if name in frame), None)
    if column is None:
        raise ValueError(f"Bloomberg PIT universe file requires security_id or ticker: {path}")
    return sorted({str(value).strip() for value in frame[column].dropna() if str(value).strip()})


def _resolve_candidates(repository: DuckDBRepository, args: argparse.Namespace) -> pd.DataFrame:
    statuses = list(args.listing_status)
    if args.include_delisted and "Delisted" not in statuses:
        statuses.append("Delisted")
    symbols = list(args.symbols)
    if args.universe_file is not None:
        symbols.extend(_load_universe_ids(args.universe_file))
    candidates = load_candidates(
        repository,
        list(args.regions),
        statuses,
        symbols,
    )
    if candidates.empty:
        return candidates
    candidates = (
        candidates.sort_values(
            ["provider_symbol", "existing_price_rows", "security_id"],
            ascending=[True, False, True],
        )
        .drop_duplicates("provider_symbol", keep="first")
        .reset_index(drop=True)
    )
    if args.max_symbols > 0:
        candidates = candidates.head(args.max_symbols).copy()
    return candidates.reset_index(drop=True)


def _write(repository: DuckDBRepository, table_name: str, frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    repository.write_table(table_name, frame, SCHEMAS[table_name].primary_key)
    return len(frame)


def _run_frame(
    run_id: str,
    started_at: pd.Timestamp,
    status: str,
    args: argparse.Namespace,
    row_count: int,
    error: str | None = None,
) -> pd.DataFrame:
    completed_at = pd.Timestamp.now("UTC").tz_localize(None) if status != "running" else pd.NaT
    return pd.DataFrame(
        [
            {
                "ingestion_run_id": run_id,
                "source_name": "bloomberg",
                "dataset_name": "production_pit_vintages",
                "started_at": started_at,
                "completed_at": completed_at,
                "status": status,
                "requested_start_date": pd.Timestamp(args.start),
                "requested_end_date": pd.Timestamp(args.end),
                "request_parameters_json": json.dumps(vars(args), default=str, sort_keys=True),
                "row_count": row_count,
                "inserted_count": row_count,
                "updated_count": 0,
                "rejected_count": 0,
                "payload_hash": None,
                "config_hash": None,
                "error_message": error,
            }
        ]
    )[list(SCHEMAS["data_ingestion_runs"].column_names)]


def _write_run(repository: DuckDBRepository, frame: pd.DataFrame) -> None:
    repository.write_table(
        "data_ingestion_runs",
        frame,
        SCHEMAS["data_ingestion_runs"].primary_key,
    )


def coverage(repository: DuckDBRepository) -> pd.DataFrame:
    rows = []
    specifications = {
        "fundamental_vintages": ("security_id", "fiscal_period_end", "available_from"),
        "corporate_action_vintages": ("security_id", "ex_date", "available_from"),
        "market_cap_vintages": ("security_id", "as_of_date", "available_from"),
        "identifier_vintages": ("security_id", "effective_from", "available_from"),
        "macro_release_vintages": ("series_id", "observation_date", "available_from"),
        "sentiment_vintages": ("security_id", "published_at", "available_from"),
        "decision_snapshot_manifests": ("model_run_id", "as_of_date", "available_from"),
    }
    for table_name, (entity_column, date_column, available_column) in specifications.items():
        result = repository.query(
            f"""
            SELECT COUNT(*) AS rows,
                   COUNT(DISTINCT {entity_column}) AS entities,
                   MIN({date_column}) AS earliest_observation,
                   MAX({date_column}) AS latest_observation,
                   MIN({available_column}) AS earliest_available_from,
                   MAX({available_column}) AS latest_available_from
            FROM {table_name}
            """
        ).iloc[0]
        rows.append({"dataset": table_name, **result.to_dict()})
    return pd.DataFrame(rows)


def main() -> int:
    args = parse_args()
    data_config = load_data_config()
    repository = DuckDBRepository(data_config.duckdb_path)
    if not args.skip_migrations:
        repository.execute_migrations(data_config.migrations_path)
    if args.coverage_only:
        report = coverage(repository)
        print(report.to_string(index=False))
        args.coverage_report.parent.mkdir(parents=True, exist_ok=True)
        report.to_csv(args.coverage_report, index=False)
        return 0

    candidates = _resolve_candidates(repository, args)
    if candidates.empty:
        raise RuntimeError("No Bloomberg-mappable securities matched the requested universe.")
    symbols = candidates["provider_symbol"].astype(str).tolist()
    symbol_to_security = dict(zip(candidates["provider_symbol"], candidates["security_id"]))
    universe_hash = _candidate_hash(candidates)
    checkpoint = Checkpoint(args.checkpoint, args.resume)
    run_id = str(uuid4())
    started_at = pd.Timestamp.now("UTC").tz_localize(None)
    _write_run(repository, _run_frame(run_id, started_at, "running", args, 0))

    adapter = BloombergDesktopAdapter(
        replace(
            BloombergConfig.from_env(),
            max_securities_per_request=max(int(args.request_size), 1),
        )
    )
    LOGGER.info("Bloomberg PIT ingestion selected %s canonical securities.", len(candidates))
    total_rows = 0
    try:
        currency_by_symbol = dict(
            zip(
                candidates["provider_symbol"].astype(str),
                candidates["trading_currency"].fillna("").astype(str),
            )
        )
        reference_payload: dict[str, object] = {}
        if {"identifiers", "corporate-actions"}.intersection(args.datasets):
            reference_fields = list(CURRENCY_FIELDS)
            if "identifiers" in args.datasets:
                reference_fields.extend(IDENTIFIER_FIELDS)
            if "corporate-actions" in args.datasets:
                reference_fields.extend(CORPORATE_ACTION_FIELDS)
            reference_payload = adapter.load_reference_data(symbols, reference_fields)
            currency_by_symbol.update(reference_currency_map(reference_payload))

        identifier_key = f"identifiers:{universe_hash}"
        if "identifiers" in args.datasets and not checkpoint.contains(identifier_key):
            identifiers = normalise_identifier_snapshot(
                reference_payload,
                symbol_to_security,
                started_at,
                run_id,
            )
            total_rows += _write(repository, "identifier_vintages", identifiers)
            LOGGER.info("Stored %s Bloomberg identifier vintages.", len(identifiers))
            checkpoint.mark(identifier_key)

        actions_key = f"corporate-actions:{universe_hash}"
        if "corporate-actions" in args.datasets and not checkpoint.contains(actions_key):
            actions = normalise_corporate_actions(
                reference_payload,
                symbol_to_security,
                currency_by_symbol,
                started_at,
                run_id,
            )
            total_rows += _write(repository, "corporate_action_vintages", actions)
            LOGGER.info("Stored %s Bloomberg corporate-action vintages.", len(actions))
            checkpoint.mark(actions_key)

        market_key = f"market-cap:{universe_hash}:{args.start}:{args.end}"
        if "market-cap" in args.datasets and not checkpoint.contains(market_key):
            market_history = adapter.load_historical_fields(
                symbols,
                MARKET_CAP_FIELDS,
                args.start,
                args.end,
                periodicity="MONTHLY",
            )
            market_cap = normalise_market_cap_history(
                market_history,
                symbol_to_security,
                currency_by_symbol,
                started_at,
                run_id,
            )
            total_rows += _write(repository, "market_cap_vintages", market_cap)
            LOGGER.info("Stored %s monthly Bloomberg market-cap vintages.", len(market_cap))
            checkpoint.mark(market_key)

        if "fundamentals" in args.datasets:
            dates = _snapshot_dates(args)
            for period_code in args.period_types:
                period_type = "quarterly" if period_code == "Q" else "annual"
                for position, snapshot_date in enumerate(dates, start=1):
                    key = f"fundamentals:{universe_hash}:{period_code}:{snapshot_date.date()}"
                    if checkpoint.contains(key):
                        continue
                    payload = adapter.load_reference_data(
                        symbols,
                        FUNDAMENTAL_FIELDS,
                        overrides={
                            "FUND_PER": period_code,
                            "FUNDAMENTAL_DATABASE_DATE": snapshot_date.strftime("%Y%m%d"),
                        },
                    )
                    if not payload:
                        error_sample = "; ".join(
                            f"{key}: {value}"
                            for key, value in list(adapter.last_errors.items())[:5]
                        )
                        raise RuntimeError(
                            f"Bloomberg returned no fundamental payload for {period_code} "
                            f"{snapshot_date.date()}. {error_sample}"
                        )
                    vintages = normalise_fundamental_snapshot(
                        payload,
                        symbol_to_security,
                        currency_by_symbol,
                        snapshot_date,
                        period_type,
                        started_at,
                        run_id,
                    )
                    total_rows += _write(repository, "fundamental_vintages", vintages)
                    total_rows += _write(
                        repository,
                        "fundamentals_reported",
                        to_model_fundamentals(vintages),
                    )
                    checkpoint.mark(key)
                    LOGGER.info(
                        "Fundamental snapshot %s/%s period=%s date=%s stored=%s.",
                        position,
                        len(dates),
                        period_code,
                        snapshot_date.date(),
                        len(vintages),
                    )
                    if args.sleep_seconds > 0:
                        time.sleep(args.sleep_seconds)

        _write_run(repository, _run_frame(run_id, started_at, "completed", args, total_rows))
    except Exception as exc:
        _write_run(repository, _run_frame(run_id, started_at, "failed", args, total_rows, str(exc)))
        raise

    report = coverage(repository)
    args.coverage_report.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.coverage_report, index=False)
    print(report.to_string(index=False))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    raise SystemExit(main())
