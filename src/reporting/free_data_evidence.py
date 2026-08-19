from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


SUMMARY_COLUMNS = (
    "source",
    "role",
    "status",
    "rows",
    "entities",
    "positive_volume_rows",
    "positive_volume_entities",
    "coverage_fraction",
    "start_date",
    "end_date",
    "evidence_semantics",
    "limitation",
)


@dataclass(frozen=True)
class FreeDataEvidenceResult:
    summary_path: Path
    manifest_path: Path
    summary: pd.DataFrame


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return payload if isinstance(payload, dict) else {}


def _query_one(repository: Any, sql: str) -> dict[str, Any]:
    try:
        frame = repository.query(sql)
    except Exception:
        return {}
    if frame.empty:
        return {}
    return frame.iloc[0].to_dict()


def _database_row(
    repository: Any,
    *,
    source: str,
    role: str,
    sql: str,
    semantics: str,
    limitation: str,
) -> dict[str, Any]:
    values = _query_one(repository, sql)
    rows = int(values.get("rows") or 0)
    return {
        "source": source,
        "role": role,
        "status": "observed" if rows else "blocked_or_unavailable",
        "rows": rows,
        "entities": int(values.get("entities") or 0),
        "positive_volume_rows": int(values.get("positive_volume_rows") or 0),
        "positive_volume_entities": int(
            values.get("positive_volume_entities") or 0
        ),
        "coverage_fraction": float("nan"),
        "start_date": values.get("start_date"),
        "end_date": values.get("end_date"),
        "evidence_semantics": semantics,
        "limitation": limitation,
    }


def collect_free_data_evidence(
    repository: Any,
    validation_directory: str | Path,
) -> pd.DataFrame:
    validation = Path(validation_directory)
    rows = [
        _database_row(
            repository,
            source="akshare",
            role="china_hk_ohlcv_turnover",
            sql="""
                SELECT COUNT(*) AS rows,
                       COUNT(DISTINCT security_id) AS entities,
                       COUNT(*) FILTER (WHERE volume > 0) AS positive_volume_rows,
                       COUNT(DISTINCT security_id) FILTER (WHERE volume > 0) AS positive_volume_entities,
                       MIN(trade_date) AS start_date,
                       MAX(trade_date) AS end_date
                FROM prices_daily
                WHERE source = 'akshare'
            """,
            semantics="observed_unadjusted_daily_bars",
            limitation="Coverage depends on public endpoint availability and does not prove historical membership.",
        ),
        _database_row(
            repository,
            source="yfinance",
            role="china_hk_ohlcv_volume",
            sql="""
                SELECT COUNT(*) AS rows,
                       COUNT(DISTINCT p.security_id) AS entities,
                       COUNT(*) FILTER (WHERE p.volume > 0) AS positive_volume_rows,
                       COUNT(DISTINCT p.security_id) FILTER (WHERE p.volume > 0) AS positive_volume_entities,
                       MIN(p.trade_date) AS start_date,
                       MAX(p.trade_date) AS end_date
                FROM prices_daily p
                JOIN securities s USING (security_id)
                WHERE p.source = 'yfinance'
                  AND s.region IN ('Mainland China', 'Hong Kong')
            """,
            semantics="observed_public_daily_bars_with_provider_volume",
            limitation="Current security mappings do not prove historical index or exchange membership.",
        ),
        _database_row(
            repository,
            source="fred_alfred",
            role="macro_release_vintages",
            sql="""
                SELECT COUNT(*) AS rows,
                       COUNT(DISTINCT series_id) AS entities,
                       MIN(observation_date) AS start_date,
                       MAX(observation_date) AS end_date
                FROM macro_release_vintages
                WHERE LOWER(source) LIKE '%fred%'
                   OR LOWER(source) LIKE '%alfred%'
            """,
            semantics="point_in_time_macro_release_vintages",
            limitation="Only configured public series are represented.",
        ),
        _database_row(
            repository,
            source="sec_edgar",
            role="us_fundamental_filing_vintages",
            sql="""
                SELECT COUNT(*) AS rows,
                       COUNT(DISTINCT security_id) AS entities,
                       MIN(fiscal_period_end) AS start_date,
                       MAX(fiscal_period_end) AS end_date
                FROM fundamental_vintages
                WHERE LOWER(source) LIKE 'sec%'
            """,
            semantics="filing_accession_vintages_when_observed",
            limitation="SEC automated-access policy or network throttling can block collection; blocked is not a pass.",
        ),
    ]

    openfigi = _read_json(validation / "openfigi_backfill_status.json")
    attempted = int(openfigi.get("attempted_jobs") or 0)
    matched = int(openfigi.get("matched_jobs") or 0)
    failed_chunks = int(openfigi.get("failed_chunks") or 0)
    rows.append(
        {
            "source": "openfigi",
            "role": "identifier_mapping",
            "status": "observed" if attempted and failed_chunks == 0 else "blocked_or_unavailable",
            "rows": int(openfigi.get("identifier_rows_written") or 0),
            "entities": matched,
            "positive_volume_rows": 0,
            "positive_volume_entities": 0,
            "coverage_fraction": matched / attempted if attempted else float("nan"),
            "start_date": None,
            "end_date": openfigi.get("generated_at"),
            "evidence_semantics": openfigi.get(
                "evidence_semantics",
                "current_snapshot_not_historical_identifier_history",
            ),
            "limitation": "Current mapping snapshot only; unmatched jobs remain visible.",
        }
    )

    openbb = _read_json(validation / "openbb_benchmark_validation.json")
    openbb_summary = openbb.get("summary")
    observations = openbb_summary if isinstance(openbb_summary, list) else []
    rows.append(
        {
            "source": "openbb",
            "role": "benchmark_normalization_validation",
            "status": str(openbb.get("status") or "blocked_or_unavailable"),
            "rows": sum(int(item.get("rows") or 0) for item in observations if isinstance(item, dict)),
            "entities": len(observations),
            "positive_volume_rows": sum(
                int(item.get("positive_volume_rows") or 0)
                for item in observations
                if isinstance(item, dict)
            ),
            "positive_volume_entities": sum(
                int(item.get("positive_volume_rows") or 0) > 0
                for item in observations
                if isinstance(item, dict)
            ),
            "coverage_fraction": (
                len(observations) / len(openbb.get("requested_symbols", []))
                if openbb.get("requested_symbols")
                else float("nan")
            ),
            "start_date": min(
                (item.get("start") for item in observations if isinstance(item, dict) and item.get("start")),
                default=None,
            ),
            "end_date": max(
                (item.get("end") for item in observations if isinstance(item, dict) and item.get("end")),
                default=None,
            ),
            "evidence_semantics": str(
                openbb.get("openbb_role")
                or "normalization_layer_not_independent_source"
            ),
            "limitation": "The named upstream provider remains the underlying observation source.",
        }
    )
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_free_data_evidence(
    repository: Any,
    validation_directory: str | Path,
    output_directory: str | Path,
) -> FreeDataEvidenceResult:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    summary = collect_free_data_evidence(repository, validation_directory)
    summary_path = output / "free_data_evidence_summary.csv"
    temporary_summary = summary_path.with_suffix(".csv.tmp")
    summary.to_csv(temporary_summary, index=False)
    temporary_summary.replace(summary_path)
    manifest_path = output / "free_data_evidence_manifest.json"
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "summary_path": summary_path.name,
        "summary_sha256": _sha256(summary_path),
        "sources": int(len(summary)),
        "observed_sources": int(summary["status"].isin(["observed", "pass"]).sum()),
        "publication_boundary": "aggregate_counts_only_no_credentials_raw_payloads_or_database",
    }
    temporary_manifest = manifest_path.with_suffix(".json.tmp")
    temporary_manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary_manifest.replace(manifest_path)
    return FreeDataEvidenceResult(summary_path, manifest_path, summary)
