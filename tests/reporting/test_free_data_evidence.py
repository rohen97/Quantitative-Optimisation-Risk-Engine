from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.reporting.free_data_evidence import build_free_data_evidence


class _Repository:
    def query(self, sql: str) -> pd.DataFrame:
        if "FROM prices_daily" in sql:
            return pd.DataFrame(
                [
                    {
                        "rows": 1000,
                        "entities": 4,
                        "positive_volume_rows": 900,
                        "positive_volume_entities": 4,
                        "start_date": "1997-01-02",
                        "end_date": "2026-07-31",
                    }
                ]
            )
        if "FROM macro_release_vintages" in sql:
            return pd.DataFrame(
                [{"rows": 500, "entities": 6, "start_date": "1994-01-01", "end_date": "2026-07-31"}]
            )
        return pd.DataFrame(
            [{"rows": 0, "entities": 0, "start_date": None, "end_date": None}]
        )


def test_free_data_evidence_is_aggregate_and_explicit(tmp_path: Path) -> None:
    validation = tmp_path / "validation"
    validation.mkdir()
    (validation / "openfigi_backfill_status.json").write_text(
        json.dumps(
            {
                "attempted_jobs": 10,
                "matched_jobs": 9,
                "identifier_rows_written": 27,
                "failed_chunks": 0,
                "evidence_semantics": "current_snapshot_not_historical_identifier_history",
            }
        ),
        encoding="utf-8",
    )
    (validation / "openbb_benchmark_validation.json").write_text(
        json.dumps(
            {
                "status": "pass",
                "requested_symbols": ["A", "B"],
                "openbb_role": "normalization_layer_not_independent_source",
                "summary": [
                    {"ticker": "A", "rows": 10, "start": "2020-01-01", "end": "2021-01-01"},
                    {"ticker": "B", "rows": 12, "start": "2020-02-01", "end": "2021-02-01"},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = build_free_data_evidence(
        _Repository(), validation, tmp_path / "output"
    )

    summary = result.summary.set_index("source")
    assert summary.loc["akshare", "rows"] == 1000
    assert summary.loc["yfinance", "positive_volume_rows"] == 900
    assert summary.loc["yfinance", "positive_volume_entities"] == 4
    assert summary.loc["openfigi", "coverage_fraction"] == 0.9
    assert summary.loc["openbb", "entities"] == 2
    assert summary.loc["sec_edgar", "status"] == "blocked_or_unavailable"
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["publication_boundary"].endswith(
        "no_credentials_raw_payloads_or_database"
    )
