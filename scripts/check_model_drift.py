from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.production.drift import run_drift_checks
from src.utils.config import ROOT, load_settings


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check Wolf model drift.")
    parser.add_argument("--mode", choices=["daily", "weekly", "monthly", "release_candidate"], default="weekly")
    parser.parse_args()
    settings = load_settings()
    checks = run_drift_checks(ROOT, settings.get("production", {}))
    print(json.dumps([check.__dict__ for check in checks], indent=2, default=str))
    sys.exit(1 if any(check.status == "FAIL" for check in checks) else 0)
