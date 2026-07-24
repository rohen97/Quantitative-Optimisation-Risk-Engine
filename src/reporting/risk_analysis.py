from __future__ import annotations

import pandas as pd

from src.reporting.models import ICDataBundle
from src.reporting.portfolio_resolver import ResolvedPortfolio


def build_risk_summary(bundle: ICDataBundle) -> dict[str, object]:
    risk = bundle.frames.get("risk_report", pd.DataFrame())
    if risk.empty:
        return {}
    row = risk.iloc[0]
    return {column: row.get(column) for column in risk.columns}


def top_risk_contributors(bundle: ICDataBundle, n: int = 10) -> pd.DataFrame:
    frame = bundle.frames.get("risk_contribution", pd.DataFrame()).copy()
    if frame.empty:
        return frame
    numeric_cols = frame.select_dtypes(include="number").columns.tolist()
    if numeric_cols:
        return frame.sort_values(numeric_cols[0], ascending=False).head(n)
    return frame.head(n)


def build_portfolio_risk_summary(bundle: ICDataBundle, resolved: ResolvedPortfolio) -> pd.DataFrame:
    risk = bundle.frames.get("risk_report", pd.DataFrame()).copy()
    if risk.empty:
        return pd.DataFrame()
    row = risk.iloc[-1].to_dict()
    row["selected_portfolio_source"] = resolved.source_name
    row["expected_volatility"] = row.get("portfolio_expected_volatility")
    row["var_5"] = row.get("portfolio_var_5")
    row["cvar_5"] = row.get("portfolio_cvar_5")
    row["expected_shortfall_5"] = row.get("portfolio_expected_shortfall_5")
    row["maximum_drawdown_proxy"] = row.get("portfolio_max_drawdown_proxy")
    row["dividend_cut_risk"] = row.get("portfolio_dividend_cut_risk")
    row["liquidity_risk"] = row.get("portfolio_liquidity_risk_score")
    row["concentration"] = row.get("HHI")
    return pd.DataFrame([row])


def build_top_risk_contributors(bundle: ICDataBundle, n: int = 10) -> pd.DataFrame:
    frame = bundle.frames.get("risk_contribution", pd.DataFrame()).copy()
    if frame.empty:
        return frame
    for column in ("risk_rank", "cvar_rank", "drawdown_rank"):
        if column not in frame:
            frame[column] = range(1, len(frame) + 1)
    numeric_cols = frame.select_dtypes(include="number").columns.tolist()
    if numeric_cols:
        frame = frame.sort_values(numeric_cols[0], ascending=False)
    return frame.head(n).reset_index(drop=True)
