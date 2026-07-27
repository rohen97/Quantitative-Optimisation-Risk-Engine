from __future__ import annotations

import json
from pathlib import Path

from ..models import ProductionAlert


class FileAlertSink:
    name = "file"

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def send(self, alert: ProductionAlert) -> dict:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(alert.__dict__, default=str, sort_keys=True) + "\n")
        return {"channel": self.name, "success": True, "error": None}
