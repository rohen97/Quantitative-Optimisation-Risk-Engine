from __future__ import annotations

from datetime import datetime, timezone

from src.production.models import ProductionRunResult
from src.production.status_report import write_global_status, write_run_status_reports


def test_status_reports_are_written(tmp_path):
    now = datetime.now(timezone.utc)
    result = ProductionRunResult("prod", "daily", "SUCCEEDED", "APPROVED", tmp_path, now, now, [], [], [], [], (), ())
    paths = write_run_status_reports(result)
    assert paths["json"].exists()
    global_paths = write_global_status(tmp_path, result, "prod", "prod")
    assert global_paths["html"].exists()
