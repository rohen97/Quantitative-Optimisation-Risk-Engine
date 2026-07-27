from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.production.health import run_health_checks
from src.utils.config import ROOT, load_settings


if __name__ == "__main__":
    settings = load_settings()
    checks = run_health_checks(ROOT, settings.get("production", {}))
    print(json.dumps([check.__dict__ for check in checks], indent=2, default=str))
    sys.exit(1 if any(check.status == "FAIL" and check.severity == "CRITICAL" for check in checks) else 0)
