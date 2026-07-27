from __future__ import annotations

import json
from urllib.request import Request, urlopen

from ..models import ProductionAlert


class SlackWebhookAlertSink:
    name = "slack"

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send(self, alert: ProductionAlert) -> dict:
        payload = {
            "text": (
                f"*Wolf Model - {alert.severity}*\n"
                f"*{alert.title}*\n"
                f"{alert.message}\n"
                f"Run: {alert.production_run_id}"
            )
        }
        request = Request(
            self.webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                success = 200 <= response.status < 300
            return {"channel": self.name, "success": success, "error": None if success else "Non-success status"}
        except Exception as error:
            return {"channel": self.name, "success": False, "error": type(error).__name__}
