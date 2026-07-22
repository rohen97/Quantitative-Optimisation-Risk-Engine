from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline import run_full_pipeline


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


FULL_PIPELINE_STAGES = [
    "Current Portfolio Engine",
    "Universe and Data Engine",
    "Financial Feature Store",
    "Sentiment and Alternative Data Engine",
    "Financial Narrative Reframing Engine",
    "Regime Analysis and Market State Engine",
    "ML Forecasting and Distributional Risk Engine",
    "Conservative Stock Scorecard",
    "Portfolio-Aware Branch",
    "Clean-Sheet Branch",
    "LLM Benchmark Branch",
    "Branch Comparison",
    "Portfolio Optimisation and Constraint Engine",
    "Risk Engine",
    "Stress Testing Engine",
    "Hedge Recommendation Engine",
    "Constrained Regime-Gated Explainable DRL Engine",
    "Final Recommendation and IC outputs",
]


if __name__ == "__main__":
    for index, stage in enumerate(FULL_PIPELINE_STAGES, start=1):
        logging.info("Full pipeline stage %02d: %s", index, stage)
    outputs = run_full_pipeline()
    logging.info("Wolf Quant MVP pipeline completed with %s output frames.", len(outputs))
