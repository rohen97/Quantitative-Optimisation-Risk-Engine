from __future__ import annotations

from datetime import datetime, timezone

from src.production.incidents import IncidentStore
from src.production.models import ProductionAlert


def test_incident_deduplicates_by_fingerprint(tmp_path):
    store = IncidentStore(tmp_path / "incidents.json")
    alert = ProductionAlert("a1", "run1", datetime.now(timezone.utc), "CRITICAL", "component", "type", "Title", "Message", "fp")
    first = store.open_or_update(alert)
    second = store.open_or_update(alert)
    assert first["incident_id"] == second["incident_id"]
    assert second["occurrence_count"] == 2


def test_incident_resolve(tmp_path):
    store = IncidentStore(tmp_path / "incidents.json")
    alert = ProductionAlert("a1", "run1", datetime.now(timezone.utc), "CRITICAL", "component", "type", "Title", "Message", "fp")
    incident = store.open_or_update(alert)
    resolved = store.resolve(incident["incident_id"], "fixed", "tester")
    assert resolved["status"] == "RESOLVED"
