from __future__ import annotations

import numpy as np
import pandas as pd


def run_llm_benchmark_branch(scorecard: pd.DataFrame, mode: str = "mock") -> pd.DataFrame:
    """Produce mock structured analyst outputs for future OpenAI/Claude integration."""
    if mode != "mock":
        raise NotImplementedError("LLM provider calls are intentionally not implemented yet.")
    data = scorecard.copy()
    data["qualitative_score"] = (
        0.35 * data["dividend_safety_score"].fillna(0)
        + 0.30 * data["cash_flow_quality_score"].fillna(0)
        + 0.20 * data["balance_sheet_strength_score"].fillna(0)
        + 0.15 * data["sentiment_alt_signal_score"].fillna(0)
    ).clip(0, 100)
    data["llm_recommendation"] = np.select(
        [
            (~data["passes_hard_filters"]) | (data["qualitative_score"] < 45),
            data["qualitative_score"] >= 68,
        ],
        ["Avoid", "Buy"],
        default="Hold",
    )
    data["llm_confidence"] = (0.55 + (data["qualitative_score"] - 50).abs() / 100).clip(0.55, 0.90)
    data["investment_thesis"] = "Mock analyst view: quality, dividends and balance-sheet resilience are reviewed against sector risk."
    data["key_risks"] = "Mock risks: valuation compression, policy/regulatory shocks, dividend sustainability and liquidity stress."
    data["dividend_safety_view"] = np.where(data["dividend_safety_score"] >= 65, "Constructive", "Needs review")
    data["cashflow_quality_view"] = np.where(data["cash_flow_quality_score"] >= 65, "Constructive", "Mixed")
    data["regulatory_governance_view"] = np.where(data["regulatory_risk_score"] > 75, "Elevated risk", "No major mock concern")
    data["bull_case"] = "Dividend quality compounds with stable cash flow."
    data["base_case"] = "Moderate total return with risk controls intact."
    data["bear_case"] = "Macro or governance shock reduces valuation and income confidence."
    columns = [
        "ticker",
        "company_name",
        "investment_thesis",
        "key_risks",
        "dividend_safety_view",
        "cashflow_quality_view",
        "regulatory_governance_view",
        "bull_case",
        "base_case",
        "bear_case",
        "qualitative_score",
        "llm_recommendation",
        "llm_confidence",
    ]
    return data[columns].sort_values("qualitative_score", ascending=False).reset_index(drop=True)
