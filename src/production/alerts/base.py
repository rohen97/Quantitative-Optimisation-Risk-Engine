from __future__ import annotations

from typing import Protocol

from ..models import ProductionAlert


class AlertSink(Protocol):
    name: str

    def send(self, alert: ProductionAlert) -> dict:
        ...


SEVERITY_ORDER = {"INFO": 10, "WARNING": 20, "CRITICAL": 30}


def severity_at_least(severity: str, minimum: str) -> bool:
    return SEVERITY_ORDER.get(severity, 0) >= SEVERITY_ORDER.get(minimum, 0)
