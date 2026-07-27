from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .models import ProductionAlert


OPEN_STATUSES = {"OPEN", "ACKNOWLEDGED"}


class IncidentStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8") or "[]")

    def save(self, incidents: list[dict]) -> None:
        self.path.write_text(json.dumps(incidents, indent=2, sort_keys=True, default=str), encoding="utf-8")

    def open_or_update(self, alert: ProductionAlert) -> dict:
        incidents = self.load()
        now = datetime.now(timezone.utc).isoformat()
        for incident in incidents:
            if incident["fingerprint"] == alert.fingerprint and incident["status"] in OPEN_STATUSES:
                incident["last_seen_at"] = now
                incident["latest_production_run_id"] = alert.production_run_id
                incident["occurrence_count"] += 1
                self.save(incidents)
                return incident
        incident = {
            "incident_id": f"incident-{uuid4().hex[:12]}",
            "fingerprint": alert.fingerprint,
            "title": alert.title,
            "component": alert.component,
            "severity": alert.severity,
            "status": "OPEN",
            "opened_at": now,
            "last_seen_at": now,
            "resolved_at": None,
            "first_production_run_id": alert.production_run_id,
            "latest_production_run_id": alert.production_run_id,
            "occurrence_count": 1,
            "resolution_note": None,
        }
        incidents.append(incident)
        self.save(incidents)
        return incident

    def resolve(self, incident_id: str, resolution_note: str, operator: str | None = None) -> dict:
        incidents = self.load()
        for incident in incidents:
            if incident["incident_id"] == incident_id:
                incident["status"] = "RESOLVED"
                incident["resolved_at"] = datetime.now(timezone.utc).isoformat()
                incident["resolution_note"] = f"{resolution_note} (operator={operator or 'unknown'})"
                self.save(incidents)
                return incident
        raise KeyError(f"Incident not found: {incident_id}")


def alert_to_record(alert: ProductionAlert, deduplicated: bool, delivery_results: list[dict]) -> dict:
    return {**asdict(alert), "deduplicated": deduplicated, "delivery_results": delivery_results}
