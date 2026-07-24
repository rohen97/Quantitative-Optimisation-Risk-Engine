from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

try:
    import streamlit as st

    STREAMLIT_AVAILABLE = True
except ImportError:  # pragma: no cover
    st = None
    STREAMLIT_AVAILABLE = False


def load_report_bundle(path: Path = Path("reports/outputs/ic/latest/report_bundle.json")) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"IC report bundle is unavailable: {path}. Run scripts/run_ic_reporting.py first.")
    return json.loads(path.read_text(encoding="utf-8"))


def _frame(bundle: dict[str, object], section: str, name: str) -> pd.DataFrame:
    value = bundle.get(section, {})
    if not isinstance(value, dict):
        return pd.DataFrame()
    data = value.get(name, [])
    return pd.DataFrame(data if isinstance(data, list) else [])


def main() -> None:
    if not STREAMLIT_AVAILABLE:
        raise RuntimeError("Streamlit is not installed. Generate the report bundle with scripts/run_ic_reporting.py or install streamlit to use dashboards/ic_dashboard.py.")
    bundle = load_report_bundle()
    summary = bundle.get("executive_summary", {})
    metadata = bundle.get("metadata", {})
    st.set_page_config(page_title="Wolf Quant IC Dashboard", layout="wide")
    st.title("Wolf Quant Investment Committee Dashboard")
    st.caption(f"Model run: {metadata.get('model_run_id', 'Unavailable')}")
    cols = st.columns(4)
    cols[0].metric("Readiness", str(summary.get("decision_readiness_status", "Unavailable")) if isinstance(summary, dict) else "Unavailable")
    cols[1].metric("Dominant Regime", str(summary.get("dominant_regime", "Unavailable")) if isinstance(summary, dict) else "Unavailable")
    cols[2].metric("Wolf Chaos", str(summary.get("wolf_chaos_index", "Unavailable")) if isinstance(summary, dict) else "Unavailable")
    cols[3].metric("Selected Source", str(metadata.get("selected_portfolio_source", "Unavailable")) if isinstance(metadata, dict) else "Unavailable")
    st.subheader("Final Portfolio")
    st.dataframe(_frame(bundle, "portfolio_tables", "final_portfolio"), use_container_width=True)
    st.subheader("Trade Recommendations")
    st.dataframe(_frame(bundle, "portfolio_tables", "final_trade_recommendations"), use_container_width=True)
    st.subheader("Stress Scenarios")
    st.dataframe(_frame(bundle, "stress_tables", "stress_scenario_summary"), use_container_width=True)
    st.subheader("DRL Governance")
    st.dataframe(_frame(bundle, "drl_governance_tables", "drl_governance_summary"), use_container_width=True)


if __name__ == "__main__":
    main()
