from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.validation.validation_pipeline import run_validation_pipeline


if __name__ == "__main__":
    result = run_validation_pipeline(execution_mode="standard", run_sensitivity=False, run_ablation=False)
    print(result.output_directory / "forecast_calibration_report.csv")
