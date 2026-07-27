from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.config import ROOT


if __name__ == "__main__":
    status_path = ROOT / "reports" / "outputs" / "production" / "status.json"
    if not status_path.exists():
        print("No production status has been generated yet.")
        sys.exit(1)
    print(status_path.read_text(encoding="utf-8"))
