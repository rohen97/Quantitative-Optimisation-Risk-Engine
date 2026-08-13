from __future__ import annotations

import pandas as pd

from scripts.run_bloomberg_backfill import (
    _read_failure_report,
    _write_failure_report,
    write_bloomberg_identifiers,
)


class _Repository:
    def __init__(self) -> None:
        self.calls = []

    def write_table(self, name, frame, primary_key):
        self.calls.append((name, frame.copy(), primary_key))


def test_failure_quarantine_preserves_unattempted_and_clears_resolved(tmp_path):
    path = tmp_path / "failures.csv"
    _write_failure_report(
        path,
        [{"security_id": "A", "provider_symbol": "A HK Equity", "error": "bad"}],
        {"A"},
    )
    _write_failure_report(
        path,
        [{"security_id": "B", "provider_symbol": "B HK Equity", "error": "bad"}],
        {"B"},
    )
    assert set(_read_failure_report(path)["security_id"]) == {"A", "B"}

    _write_failure_report(path, [], {"A"})
    assert _read_failure_report(path)["security_id"].tolist() == ["B"]

    _write_failure_report(path, [], {"B"})
    assert not path.exists()


def test_bloomberg_identifier_rows_match_repository_schema():
    repository = _Repository()
    count = write_bloomberg_identifiers(
        repository,
        pd.DataFrame(
            {
                "security_id": ["0700.HK", "000001.SHE"],
                "provider_symbol": ["700 HK Equity", "000001 CH Equity"],
            }
        ),
    )
    assert count == 2
    name, frame, primary_key = repository.calls[0]
    assert name == "security_identifiers"
    assert primary_key == (
        "security_id",
        "identifier_type",
        "identifier_value",
        "valid_from",
    )
    assert frame["identifier_type"].eq("bloomberg_ticker").all()
    assert frame["source"].eq("bloomberg_mapping").all()
