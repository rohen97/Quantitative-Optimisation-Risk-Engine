from __future__ import annotations

from datetime import datetime, timezone

from src.production.manifest import write_manifest
from src.production.models import ProductionRunContext, ProductionRunResult


def test_manifest_is_written(tmp_path):
    now = datetime.now(timezone.utc)
    context = ProductionRunContext("prod", "daily", "smoke", now, now, tmp_path, tmp_path, tmp_path, "hash", "commit", False, "host", 1)
    result = ProductionRunResult("prod", "daily", "SUCCEEDED", "APPROVED", tmp_path, now, now, [], [], [], [], (), ())
    path = write_manifest(context, result)
    assert path.exists()
    assert "prod" in path.read_text(encoding="utf-8")
