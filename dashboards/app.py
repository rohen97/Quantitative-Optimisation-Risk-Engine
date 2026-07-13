from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st


OUTPUT_DIR = Path("reports/outputs")

st.set_page_config(page_title="Wolf Quant Model", layout="wide")
st.title("The Wolf Quant Model")

page = st.sidebar.radio(
    "Page",
    [
        "Executive Summary",
        "Current Portfolio Diagnostics",
        "Stock Recommendations",
        "Portfolio Optimisation",
        "Risk Analysis",
        "Stress Tests",
        "Hedge Book",
        "Model Validation",
    ],
)

mapping = {
    "Executive Summary": "stock_scorecard.csv",
    "Current Portfolio Diagnostics": "current_portfolio_diagnostics.csv",
    "Stock Recommendations": "recommendations_12m.csv",
    "Portfolio Optimisation": "proposed_portfolio.csv",
    "Risk Analysis": "portfolio_risk_report.csv",
    "Stress Tests": "stress_test_report.csv",
    "Hedge Book": "hedge_recommendations.csv",
}

if page == "Model Validation":
    path = OUTPUT_DIR / "model_validation_report.md"
    st.markdown(path.read_text(encoding="utf-8") if path.exists() else "Run the pipeline to create validation output.")
else:
    path = OUTPUT_DIR / mapping[page]
    if path.exists():
        st.dataframe(pd.read_csv(path), use_container_width=True)
    else:
        st.info("Run `python scripts/run_full_pipeline.py` to generate dashboard data.")
