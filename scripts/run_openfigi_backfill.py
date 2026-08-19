from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import re
import sys
import time
from uuid import uuid4

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DuckDBRepository
from src.data.schemas import SCHEMAS
from src.data_ingestion.free_market_adapters import OpenFigiMappingClient
from src.data_ingestion.http_client import DataSourceRequestError, HttpClient, HttpClientConfig
from src.utils.config import ROOT
from src.utils.env import get_env


LOGGER = logging.getLogger(__name__)
DEFAULT_REGIONS = ("US", "UK", "DACH", "EU ex-DACH", "Mainland China", "Hong Kong")
EXCHANGE_MIC = {
    "AS": "XAMS",
    "BR": "XBRU",
    "CO": "XCSE",
    "DU": "XDUS",
    "F": "XFRA",
    "HA": "XHAN",
    "HE": "XHEL",
    "HK": "XHKG",
    "HM": "XHAM",
    "IR": "XDUB",
    "LSE": "XLON",
    "MC": "XMAD",
    "MU": "XMUN",
    "PA": "XPAR",
    "SHE": "XSHE",
    "SHG": "XSHG",
    "ST": "XSTO",
    "STU": "XSTU",
    "SW": "XSWX",
    "VI": "XWBO",
    "XETRA": "XETR",
}


def _api_key_configured() -> bool:
    return bool(get_env("OPENFIGI_API_KEY", "") or get_env("OPEN_FIGI_API_KEY", ""))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Checkpoint current FIGI mappings without claiming historical coverage."
    )
    parser.add_argument("--regions", nargs="+", default=list(DEFAULT_REGIONS))
    parser.add_argument("--listing-status", nargs="+", default=["Active", "Inactive"])
    parser.add_argument("--max-symbols", type=int, default=0)
    parser.add_argument(
        "--anonymous-cap",
        type=int,
        default=25,
        help="Safety cap when OPENFIGI_API_KEY is absent; 0 explicitly permits an uncapped anonymous run.",
    )
    parser.add_argument("--chunk-size", type=int, default=0)
    parser.add_argument("--request-pause-seconds", type=float, default=None)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--skip-migrations", action="store_true")
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path("reports/outputs/validation/openfigi_backfill_status.json"),
    )
    return parser.parse_args()


def _sql_values(values: list[str]) -> str:
    return ", ".join(f"'{str(value).replace(chr(39), chr(39) * 2)}'" for value in values)


def _candidates(
    repository: DuckDBRepository,
    regions: list[str],
    statuses: list[str],
    *,
    resume: bool,
) -> pd.DataFrame:
    frame = repository.query(
        f"""
        WITH identifiers AS (
            SELECT security_id,
                   MAX(identifier_value) FILTER (WHERE identifier_type = 'isin') AS isin,
                   MAX(identifier_value) FILTER (WHERE identifier_type = 'yfinance_ticker') AS ticker
            FROM security_identifiers
            GROUP BY security_id
        )
        SELECT s.security_id,
               s.region,
               s.exchange_code,
               s.trading_currency AS currency,
               identifiers.isin,
               identifiers.ticker
        FROM securities s
        JOIN identifiers USING (security_id)
        WHERE s.instrument_type = 'Equity'
          AND s.region IN ({_sql_values(regions)})
          AND s.listing_status IN ({_sql_values(statuses)})
        ORDER BY s.region, s.exchange_code, s.security_id
        """
    )
    if resume and not frame.empty:
        completed = repository.query(
            """
            SELECT DISTINCT security_id
            FROM identifier_vintages
            WHERE source = 'openfigi_current_snapshot'
            """
        )
        if not completed.empty:
            frame = frame.loc[
                ~frame["security_id"].astype(str).isin(completed["security_id"].astype(str))
            ]

    rows: list[dict[str, object]] = []
    for row in frame.to_dict("records"):
        isin = str(row.get("isin") or "").strip().upper()
        ticker = str(row.get("ticker") or "").strip().upper()
        if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", isin):
            rows.append(
                {
                    "security_id": row["security_id"],
                    "id_type": "ID_ISIN",
                    "id_value": isin,
                }
            )
            continue
        if not ticker:
            continue
        code = ticker.split(".", 1)[0]
        candidate = {
            "security_id": row["security_id"],
            "id_type": "TICKER",
            "id_value": code,
            "currency": row.get("currency"),
        }
        mic = EXCHANGE_MIC.get(str(row.get("exchange_code") or "").upper())
        if mic:
            candidate["mic_code"] = mic
        rows.append(candidate)
    return pd.DataFrame(rows)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path = path if path.is_absolute() else ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = load_data_config()
    repository = DuckDBRepository(config.duckdb_path)
    if not args.skip_migrations:
        repository.execute_migrations(config.migrations_path)
    authenticated = _api_key_configured()
    candidates = _candidates(
        repository,
        list(args.regions),
        list(args.listing_status),
        resume=not args.no_resume,
    )
    eligible_count = len(candidates)
    applied_cap = args.max_symbols if args.max_symbols > 0 else None
    anonymous_limited = False
    if not authenticated and applied_cap is None and args.anonymous_cap > 0:
        applied_cap = args.anonymous_cap
        anonymous_limited = eligible_count > args.anonymous_cap
    if applied_cap is not None:
        candidates = candidates.head(applied_cap)
    chunk_size = args.chunk_size if args.chunk_size > 0 else (500 if authenticated else 5)
    pause = args.request_pause_seconds
    if pause is None:
        pause = 0.3 if authenticated else 12.1

    client = OpenFigiMappingClient(
        HttpClient(HttpClientConfig(timeout_seconds=30, retry_attempts=3)),
        request_pause_seconds=args.request_pause_seconds,
    )
    retrieved_at = pd.Timestamp(datetime.now(UTC)).tz_localize(None)
    run_id = str(uuid4())
    written = 0
    matched = 0
    requests = 0
    failed_chunks = 0
    warning_samples: list[str] = []
    started_at = datetime.now(UTC)
    for offset in range(0, len(candidates), chunk_size):
        chunk = candidates.iloc[offset : offset + chunk_size]
        try:
            result = client.map_identifiers(
                chunk,
                retrieved_at=retrieved_at,
                ingestion_run_id=run_id,
            )
            if not result.identifiers.empty:
                repository.write_table(
                    "identifier_vintages",
                    result.identifiers,
                    SCHEMAS["identifier_vintages"].primary_key,
                )
                written += len(result.identifiers)
            matched += result.matched_jobs
            requests += result.request_count
            warning_samples.extend(result.warnings[: max(20 - len(warning_samples), 0)])
            LOGGER.info(
                "OpenFIGI chunk %s-%s matched %s/%s jobs and wrote %s identifier rows.",
                offset + 1,
                offset + len(chunk),
                result.matched_jobs,
                result.jobs,
                len(result.identifiers),
            )
        except (DataSourceRequestError, ValueError) as exc:
            failed_chunks += 1
            warning_samples.append(f"chunk {offset + 1}: {exc}")
            LOGGER.warning("OpenFIGI chunk %s failed: %s", offset + 1, exc)
        _write_json(
            args.report_path,
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "started_at": started_at.isoformat(),
                "authenticated": authenticated,
                "eligible_remaining_at_start": eligible_count,
                "attempted_jobs": min(offset + len(chunk), len(candidates)),
                "matched_jobs": matched,
                "identifier_rows_written": written,
                "request_count": requests,
                "failed_chunks": failed_chunks,
                "anonymous_safety_cap_applied": anonymous_limited,
                "warning_samples": warning_samples[:20],
                "evidence_semantics": "current_snapshot_not_historical_identifier_history",
            },
        )
        if offset + chunk_size < len(candidates) and pause > 0:
            time.sleep(pause)
    if candidates.empty:
        _write_json(
            args.report_path,
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "started_at": started_at.isoformat(),
                "authenticated": authenticated,
                "eligible_remaining_at_start": eligible_count,
                "attempted_jobs": 0,
                "matched_jobs": 0,
                "identifier_rows_written": 0,
                "request_count": 0,
                "failed_chunks": 0,
                "anonymous_safety_cap_applied": anonymous_limited,
                "warning_samples": [],
                "evidence_semantics": "current_snapshot_not_historical_identifier_history",
            },
        )
    return 1 if failed_chunks else 0


if __name__ == "__main__":
    raise SystemExit(main())
