from pathlib import Path

import pandas as pd

from src.branches.branch_comparison import classify_branch
from src.pipeline import run_full_pipeline


def test_branch_comparison_classifies_stocks():
    row = pd.Series(
        {
            "portfolio_aware_recommendation": "Buy",
            "clean_sheet_recommendation": "Buy",
            "llm_recommendation": "Buy",
        }
    )
    assert classify_branch(row) == "Consensus Buy"

    caution = pd.Series(
        {
            "portfolio_aware_recommendation": "Buy",
            "clean_sheet_recommendation": "Hold",
            "llm_recommendation": "Avoid",
        }
    )
    assert classify_branch(caution) == "Quant Buy / LLM Caution"


def test_full_pipeline_creates_branch_outputs(tmp_path):
    run_full_pipeline(tmp_path)
    expected = [
        "recommendations_portfolio_aware.csv",
        "recommendations_clean_sheet.csv",
        "recommendations_llm_benchmark.csv",
        "branch_comparison_report.csv",
        "final_recommendations.csv",
    ]
    for filename in expected:
        assert (Path(tmp_path) / filename).exists()
