from __future__ import annotations

from datetime import datetime, timezone

from src.production.models import ProductionRunContext
from src.production.run_registry import ProductionRunRegistry


def test_run_registry_records_events(tmp_path):
    registry = ProductionRunRegistry(tmp_path / "registry.jsonl")
    context = ProductionRunContext(
        "prod-test",
        "daily",
        "smoke",
        datetime.now(timezone.utc),
        datetime.now(timezone.utc),
        tmp_path,
        tmp_path,
        tmp_path,
        "hash",
        "commit",
        False,
        "host",
        1,
    )
    registry.register_run(context, "duckdb")
    registry.complete_run("prod-test", "SUCCEEDED", "APPROVED")
    events = registry.load_events()
    assert [event["event_type"] for event in events] == ["run_registered", "run_completed"]
