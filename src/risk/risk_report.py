from __future__ import annotations

import pandas as pd


def format_risk_report(report: pd.DataFrame) -> pd.DataFrame:
    return report.copy()


def _markdown_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "No data available."
    data = frame.head(max_rows) if max_rows else frame
    columns = [str(col) for col in data.columns]
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in data.columns) + " |")
    return "\n".join(lines)


def build_risk_stress_hedge_summary(
    risk_report: pd.DataFrame,
    risk_contributions: pd.DataFrame,
    stress_report: pd.DataFrame,
    hedge_recommendations: pd.DataFrame,
    substitutions: pd.DataFrame,
) -> str:
    """Build markdown summary for risk, stress and hedge outputs."""
    worst = stress_report.head(5) if not stress_report.empty else pd.DataFrame()
    top_risk = risk_contributions.head(10) if not risk_contributions.empty else pd.DataFrame()
    lines = [
        "# Risk, Stress Testing & Hedge Summary",
        "",
        "## Executive Summary",
        "Deterministic mock risk engine identifies portfolio downside drivers, stress losses and hedge/substitution actions.",
        "",
        "## Portfolio Risk Snapshot",
        _markdown_table(risk_report),
        "",
        "## Top 10 Risk Contributors",
        _markdown_table(top_risk),
        "",
        "## Worst Stress Scenarios",
        _markdown_table(worst[["scenario_name", "portfolio_loss_pct", "portfolio_loss_usd", "risk_level", "hedge_required_flag"]])
        if not worst.empty
        else "No stress report available.",
        "",
        "## Recommended Hedges",
        _markdown_table(hedge_recommendations, 10),
        "",
        "## Defensive Substitutions",
        _markdown_table(substitutions, 10) if not substitutions.empty else "No defensive substitutions required.",
        "",
        "## Residual Risks",
        "- Mock stress shocks are deterministic approximations.",
        "- Optional institutional hedges are not executable without mandate, pricing and market data.",
        "- Real covariance, historical replay and option pricing are future upgrades.",
        "",
        "## Next Actions",
        "Review highest-loss scenarios, reduce flagged names, consider equity-only defensive substitutions and decide whether optional institutional hedges are in mandate.",
        "",
    ]
    return "\n".join(lines)
