from __future__ import annotations

from datetime import datetime, timezone

from src.production.alerts.router import AlertRouter
from src.production.models import ProductionAlert


class MemorySink:
    name = "memory"

    def __init__(self):
        self.sent = []

    def send(self, alert):
        self.sent.append(alert)
        return {"channel": self.name, "success": True}


def test_alert_router_deduplicates_recent_alerts(tmp_path):
    sink = MemorySink()
    router = AlertRouter(tmp_path / "alerts.jsonl", [(sink, "INFO")])
    alert = ProductionAlert("a1", "run", datetime.now(timezone.utc), "WARNING", "component", "type", "Title", "Message", "same")
    first = router.route(alert)
    second = router.route(alert)
    assert first["deduplicated"] is False
    assert second["deduplicated"] is True
    assert len(sink.sent) == 1
