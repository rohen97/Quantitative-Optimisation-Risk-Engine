from __future__ import annotations

from src.production.freshness import run_freshness_checks


def test_freshness_reports_missing_outputs(tmp_path):
    results = run_freshness_checks(tmp_path, {"freshness": {}})
    assert results
    assert any(result.status == "FAIL" for result in results)
