from __future__ import annotations

from ..models import ProductionAlert


class ConsoleAlertSink:
    name = "console"

    def send(self, alert: ProductionAlert) -> dict:
        print(f"[Wolf Model][{alert.severity}] {alert.title}: {alert.message}")
        return {"channel": self.name, "success": True, "error": None}
