from __future__ import annotations

from pathlib import Path

import pandas as pd


def _value(value: object) -> str:
    if value is None:
        return "Unavailable"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _table(frame: pd.DataFrame, max_rows: int = 10) -> str:
    if frame.empty:
        return "Data unavailable for this model run."
    data = frame.head(max_rows).astype(str)
    columns = [str(column) for column in data.columns]
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    rows = ["| " + " | ".join(str(value) for value in row) + " |" for row in data.to_numpy()]
    return "\n".join([header, separator, *rows])


def render_markdown_summary(context: dict[str, object], output_path: Path) -> Path:
    summary = context.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}

    lines = [
        "# Investment Committee Summary",
        "",
        f"Model run ID: `{context.get('model_run_id', 'unknown')}`",
        "",
        "## Executive Summary",
        "",
        f"- Decision readiness: {_value(summary.get('decision_readiness_status', 'Review required'))}",
        f"- Top recommendation: {_value(summary.get('top_recommendation'))}",
        f"- Dominant regime: {_value(summary.get('dominant_regime'))}",
        f"- Wolf Chaos Index: {_value(summary.get('wolf_chaos_index'))}",
        f"- DRL status: {_value(summary.get('drl_status'))}",
        f"- Portfolio VaR 5%: {_value(summary.get('portfolio_var_5'))}",
        f"- Portfolio CVaR 5%: {_value(summary.get('portfolio_cvar_5'))}",
        "",
        "## Final Portfolio",
        "",
        _table(context.get("final_portfolio", pd.DataFrame()) if isinstance(context.get("final_portfolio"), pd.DataFrame) else pd.DataFrame()),
        "",
        "## Worst Stress Scenarios",
        "",
        _table(context.get("worst_stress", pd.DataFrame()) if isinstance(context.get("worst_stress"), pd.DataFrame) else pd.DataFrame()),
        "",
        "## Data Quality",
        "",
        _table(context.get("data_quality", pd.DataFrame()) if isinstance(context.get("data_quality"), pd.DataFrame) else pd.DataFrame()),
        "",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
