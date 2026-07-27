from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.production.alerts.console import ConsoleAlertSink
from src.production.alerts.router import AlertRouter
from src.production.models import ProductionAlert
from src.utils.config import ROOT, load_settings


if __name__ == "__main__":
    settings = load_settings()
    path = ROOT / settings.get("production", {}).get("alerts", {}).get("file", {}).get("path", "reports/outputs/production/alerts.jsonl")
    router = AlertRouter(path, [(ConsoleAlertSink(), "INFO")])
    alert = ProductionAlert(f"alert-{uuid4().hex[:12]}", None, datetime.now(timezone.utc), "INFO", "test", "test_alert", "Wolf test alert", "This is a local test alert.", "test:test_alert")
    print(router.route(alert))
