from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
from uuid import uuid4

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DuckDBRepository
from src.data.schemas import SCHEMAS
from src.data_ingestion.external_adapters import FredAdapter
from src.data_ingestion.http_client import DataSourceRequestError, HttpClient, HttpClientConfig
from src.data_ingestion.macro_vintages import normalise_macro_release_vintages
from src.data_ingestion.provider_registry import load_data_source_registry


LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resumably ingest FRED real-time macro release vintages into DuckDB."
    )
    parser.add_argument("--start", default="1994-01-01")
    parser.add_argument("--end", default=pd.Timestamp.today().date().isoformat())
    parser.add_argument("--series", nargs="*", default=[])
    parser.add_argument("--skip-migrations", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path("data/locks/macro_vintage_checkpoint.json"),
    )
    parser.add_argument(
        "--status-report",
        type=Path,
        default=Path("reports/outputs/macro_vintage_backfill_status.csv"),
    )
    return parser.parse_args()


def _load_checkpoint(path: Path, enabled: bool) -> set[str]:
    if not enabled or not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {str(item) for item in payload.get("completed", [])}
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        LOGGER.warning("Ignoring unreadable macro-vintage checkpoint %s.", path)
        return set()


def _save_checkpoint(path: Path, completed: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps({"completed": sorted(completed)}, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _stored_row_count(repository: DuckDBRepository, series_id: str) -> int:
    result = repository.query(
        "SELECT COUNT(*) AS row_count FROM macro_release_vintages WHERE series_id = ?",
        [series_id],
    )
    return int(result.iloc[0]["row_count"]) if not result.empty else 0


def main() -> int:
    args = parse_args()
    registry = load_data_source_registry()
    provider = registry.providers["fred"]
    configured = {
        str(label): str(series_id)
        for label, series_id in dict(provider.settings.get("series", {})).items()
    }
    selected_ids = set(args.series)
    selected = {
        label: series_id
        for label, series_id in configured.items()
        if not selected_ids or label in selected_ids or series_id in selected_ids
    }
    unknown = selected_ids.difference(set(configured)).difference(set(configured.values()))
    if unknown:
        raise ValueError(f"Unknown configured FRED series: {', '.join(sorted(unknown))}")
    if not selected:
        raise ValueError("No FRED series selected.")
    non_revising = {
        str(series_id) for series_id in provider.settings.get("non_revising_series", [])
    }

    policy = registry.policy
    client = HttpClient(
        HttpClientConfig(
            timeout_seconds=max(int(policy.get("request_timeout_seconds", 30)), 30),
            retry_attempts=int(policy.get("retry_attempts", 3)),
            retry_backoff_seconds=float(policy.get("retry_backoff_seconds", 1.0)),
            user_agent=str(policy.get("user_agent", "wolf-quant-model/1.0")),
        )
    )
    adapter = FredAdapter(provider, client)
    data_config = load_data_config()
    repository = DuckDBRepository(data_config.duckdb_path)
    if not args.skip_migrations:
        repository.execute_migrations(data_config.migrations_path)

    resume = not args.no_resume
    completed = _load_checkpoint(args.checkpoint, resume)
    statuses: list[dict[str, object]] = []
    failed = 0
    for label, series_id in selected.items():
        mode = "observation_date" if series_id in non_revising else "alfred_vintages"
        key = f"fred:{series_id}:{mode}:{args.start}:{args.end}"
        if key in completed:
            statuses.append(
                {
                    "label": label,
                    "series_id": series_id,
                    "status": "stored_complete",
                    "rows": _stored_row_count(repository, series_id),
                    "error": "",
                }
            )
            continue
        ingestion_run_id = str(uuid4())
        LOGGER.info("Pulling FRED vintages label=%s series=%s.", label, series_id)
        try:
            observations = adapter.load_series(
                series_id,
                args.start,
                args.end,
                preserve_vintages=series_id not in non_revising,
            )
            observations["ingestion_run_id"] = ingestion_run_id
            vintages = normalise_macro_release_vintages(observations, ingestion_run_id)
            repository.write_table(
                "macro_observations", observations, SCHEMAS["macro_observations"].primary_key
            )
            repository.write_table(
                "macro_release_vintages",
                vintages,
                SCHEMAS["macro_release_vintages"].primary_key,
            )
            completed.add(key)
            _save_checkpoint(args.checkpoint, completed)
            statuses.append(
                {"label": label, "series_id": series_id, "status": "completed", "rows": len(vintages), "error": ""}
            )
            LOGGER.info("Stored %s FRED release vintages for %s.", len(vintages), series_id)
        except (DataSourceRequestError, ValueError, KeyError) as exc:
            failed += 1
            statuses.append(
                {"label": label, "series_id": series_id, "status": "failed", "rows": 0, "error": str(exc)}
            )
            LOGGER.warning("FRED series %s failed: %s", series_id, exc)

    report = pd.DataFrame(statuses)
    args.status_report.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.status_report, index=False)
    print(report.to_string(index=False))
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    raise SystemExit(main())
