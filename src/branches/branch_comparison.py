from __future__ import annotations

import numpy as np
import pandas as pd


def classify_branch(row: pd.Series) -> str:
    pa_buy = row["portfolio_aware_recommendation"] == "Buy"
    clean_buy = row["clean_sheet_recommendation"] == "Buy"
    llm_buy = row["llm_recommendation"] == "Buy"
    quant_buy = pa_buy or clean_buy
    if pa_buy and clean_buy and llm_buy:
        return "Consensus Buy"
    if quant_buy and row["llm_recommendation"] == "Avoid":
        return "Quant Buy / LLM Caution"
    if llm_buy and not quant_buy:
        return "LLM Buy / Quant Reject"
    if pa_buy and not clean_buy:
        return "Portfolio-Aware Only"
    if clean_buy and not pa_buy:
        return "Clean-Sheet Only"
    return "Reject"


def compare_branches(
    portfolio_aware: pd.DataFrame,
    clean_sheet: pd.DataFrame,
    llm_benchmark: pd.DataFrame,
) -> pd.DataFrame:
    """Compare recommendation branches and flag disagreements for review."""
    data = portfolio_aware.rename(columns={"recommendation": "portfolio_aware_recommendation"}).merge(
        clean_sheet[["ticker", "clean_sheet_recommendation", "clean_sheet_score", "clean_sheet_rank", "clean_sheet_target_weight"]],
        on="ticker",
        how="outer",
    )
    data = data.merge(
        llm_benchmark[["ticker", "qualitative_score", "llm_recommendation", "llm_confidence"]],
        on="ticker",
        how="outer",
    )
    rec_cols = ["portfolio_aware_recommendation", "clean_sheet_recommendation", "llm_recommendation"]
    data[rec_cols] = data[rec_cols].fillna("Avoid")
    data["branch_classification"] = data.apply(classify_branch, axis=1)
    data["recommendation_agreement"] = data[rec_cols].nunique(axis=1).rsub(4) / 3
    score_cols = ["portfolio_aware_score", "clean_sheet_score", "qualitative_score"]
    data["score_dispersion"] = data[score_cols].std(axis=1).fillna(0)
    data["llm_score"] = data["qualitative_score"]
    data["disagreement_flag"] = data[rec_cols].nunique(axis=1) > 1
    data["final_review_required"] = data["disagreement_flag"] | data["branch_classification"].isin(
        ["LLM Buy / Quant Reject", "Quant Buy / LLM Caution"]
    )
    return data[
        [
            "ticker",
            "company_name",
            "portfolio_aware_recommendation",
            "clean_sheet_recommendation",
            "llm_recommendation",
            "branch_classification",
            "recommendation_agreement",
            "score_dispersion",
            "portfolio_aware_rank",
            "clean_sheet_rank",
            "llm_score",
            "disagreement_flag",
            "final_review_required",
            "target_weight_portfolio_aware",
            "clean_sheet_target_weight",
        ]
    ].sort_values(["final_review_required", "recommendation_agreement", "llm_score"], ascending=[False, False, False]).reset_index(drop=True)


def build_final_recommendations(branch_comparison: pd.DataFrame, scorecard: pd.DataFrame) -> pd.DataFrame:
    """Create final recommendations with quant risk controls ahead of LLM agreement."""
    data = branch_comparison.merge(
        scorecard[
            [
                "ticker",
                "passes_hard_filters",
                "dividend_safety_score",
                "cash_flow_quality_score",
                "balance_sheet_strength_score",
                "final_recommendation_score",
                "risk_management_flags",
            ]
        ],
        on="ticker",
        how="left",
    )
    quant_buy = data["portfolio_aware_recommendation"].eq("Buy")
    llm_support = data["llm_recommendation"].eq("Buy") & ~data["final_review_required"]
    data["final_recommendation"] = np.select(
        [
            ~data["passes_hard_filters"].fillna(False),
            quant_buy & llm_support,
            quant_buy,
        ],
        ["Avoid", "Buy", "Hold"],
        default="Avoid",
    )
    data["final_target_weight"] = np.where(data["final_recommendation"].eq("Buy"), data["target_weight_portfolio_aware"], 0.0)
    data["confidence_adjustment"] = np.where(llm_support, "LLM agreement improves confidence", "Review required or no LLM support")
    return data.sort_values("final_recommendation_score", ascending=False).reset_index(drop=True)
