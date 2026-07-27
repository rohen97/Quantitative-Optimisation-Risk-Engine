from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.production.incidents import IncidentStore
from src.utils.config import ROOT


parser = argparse.ArgumentParser(description="Resolve a Wolf production incident.")
parser.add_argument("--incident-id", required=True)
parser.add_argument("--resolution-note", required=True)
parser.add_argument("--operator", default=None)


if __name__ == "__main__":
    args = parser.parse_args()
    store = IncidentStore(ROOT / "reports" / "outputs" / "production" / "incidents.json")
    print(store.resolve(args.incident_id, args.resolution_note, args.operator))
