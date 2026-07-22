from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.drl.drl_pipeline import run_drl_pipeline


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


if __name__ == "__main__":
    outputs = run_drl_pipeline()
    logging.info("DRL explanation rows: %s", len(outputs["drl_explanations"]))
