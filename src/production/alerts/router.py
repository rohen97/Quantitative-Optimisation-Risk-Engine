from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..incidents import IncidentStore
from ..models import ProductionAlert
from .base import AlertSink, severity_at_least


class AlertRouter:
    def __init__(
        self,
        alert_log_path: Path,
        sinks: list[tuple[AlertSink, str]],
        deduplication_window_minutes: int = 120,
        incident_store: IncidentStore | None = None,
    ) -> None:
        self.alert_log_path = alert_log_path
        self.alert_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.sinks = sinks
        self.deduplication_window = timedelta(minutes=deduplication_window_minutes)
        self.incident_store = incident_store

    def _recent_matching_alert_exists(self, alert: ProductionAlert) -> bool:
        if not self.alert_log_path.exists():
            return False
        cutoff = datetime.now(timezone.utc) - self.deduplication_window
        for line in self.alert_log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                created_at = datetime.fromisoformat(row["created_at"])
            except Exception:
                continue
            if row.get("fingerprint") == alert.fingerprint and created_at.astimezone(timezone.utc) >= cutoff:
                return True
        return False

    def route(self, alert: ProductionAlert) -> dict:
        deduplicated = self._recent_matching_alert_exists(alert)
        delivery_results: list[dict] = []
        if not deduplicated:
            for sink, minimum_severity in self.sinks:
                if severity_at_least(alert.severity, minimum_severity):
                    delivery_results.append(sink.send(alert))
            if alert.severity == "CRITICAL" and self.incident_store is not None:
                incident = self.incident_store.open_or_update(alert)
                delivery_results.append({"channel": "incident_store", "success": True, "incident_id": incident["incident_id"]})
        record = {
            **alert.__dict__,
            "created_at": alert.created_at.isoformat(),
            "deduplicated": deduplicated,
            "delivery_results": delivery_results,
        }
        with self.alert_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        return record
