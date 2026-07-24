from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.config import ROOT
from src.validation.leakage import leakage_report, validate_point_in_time


if __name__ == "__main__":
    features = pd.read_csv(ROOT / "reports" / "outputs" / "features_monthly.csv")
    print(leakage_report(features).to_string(index=False))
    print(validate_point_in_time(features).to_string(index=False))
