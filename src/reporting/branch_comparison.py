from __future__ import annotations

import pandas as pd

from src.reporting.column_resolver import canonicalise_dataframe
from src.reporting.models import ICDataBundle
from src.reporting.portfolio_resolver import ResolvedPortfolio


def build_branch_comparison(bundle: ICDataBundle) -> pd.DataFrame:
    branch = bundle.frames.get("branch_comparison", pd.DataFrame()).copy()
    if branch.empty:
        return branch
    keep = [column for column in ["ticker", "company_name", "portfolio_aware_recommendation", "clean_sheet_recommendation", "llm_recommendation", "branch_classification", "recommendation_agreement", "disagreement_flag"] if column in branch]
    return branch[keep].copy()


def _as_security_frame(frame: pd.DataFrame, prefix: str, weight_col: str | None = None, rec_col: str | None = None) -> pd.DataFrame:
    data = canonicalise_dataframe(frame)
    if data.empty:
        return pd.DataFrame(columns=["security_id"])
    if "security_id" not in data:
        data["security_id"] = data.get("ticker", pd.Series(range(len(data)), index=data.index)).astype(str)
    output = data[["security_id"]].copy()
    if "ticker" in data:
        output["ticker"] = data["ticker"].astype(str)
    if rec_col and rec_col in data:
        output[f"{prefix}_recommendation"] = data[rec_col].astype(str)
    elif "recommendation" in data:
        output[f"{prefix}_recommendation"] = data["recommendation"].astype(str)
    if weight_col and weight_col in data:
        output[f"{prefix}_weight"] = pd.to_numeric(data[weight_col], errors="coerce").fillna(0.0)
    elif "target_weight" in data:
        output[f"{prefix}_weight"] = pd.to_numeric(data["target_weight"], errors="coerce").fillna(0.0)
    return output.drop_duplicates("security_id")


def _consensus(row: pd.Series) -> str:
    pa = str(row.get("portfolio_aware_recommendation", "")).lower()
    cs = str(row.get("clean_sheet_recommendation", "")).lower()
    llm = str(row.get("llm_recommendation", "")).lower()
    opt = float(row.get("optimiser_weight", 0.0) or 0.0)
    drl = float(row.get("drl_weight", 0.0) or 0.0)
    final = float(row.get("final_weight", 0.0) or 0.0)
    text = " ".join([pa, cs, llm])
    if "exclude" in text or "avoid" in text and final <= 1e-10:
        return "Hard Risk Exclusion"
    if "buy" in pa and "buy" in cs:
        return "Consensus Buy"
    if "hold" in pa and "hold" in cs:
        return "Consensus Hold"
    if any(word in pa for word in ("reduce", "sell", "exit")) and any(word in cs for word in ("reduce", "sell", "exit")):
        return "Consensus Reduce"
    if "buy" in pa and "buy" not in cs:
        return "Portfolio-Aware Only"
    if "buy" in cs and "buy" not in pa:
        return "Clean-Sheet Only"
    if opt - final > 0.01:
        return "Optimiser Overweight"
    if drl - opt > 0.01:
        return "DRL Overweight"
    if opt - drl > 0.01:
        return "DRL Underweight"
    if ("buy" in pa or "buy" in cs) and any(word in llm for word in ("avoid", "caution", "reduce")):
        return "Quant Buy / LLM Caution"
    if any(word in pa + cs for word in ("avoid", "reduce")) and "buy" in llm:
        return "Quant Caution / LLM Buy"
    return "No Consensus"


def build_model_branch_comparison(bundle: ICDataBundle, resolved: ResolvedPortfolio) -> pd.DataFrame:
    selected_ids = set(resolved.portfolio.get("security_id", pd.Series(dtype=str)).dropna().astype(str))
    selected_tickers = set(resolved.portfolio.get("ticker", pd.Series(dtype=str)).dropna().astype(str))

    def selected(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty or not (selected_ids or selected_tickers):
            return frame
        keep = frame["security_id"].astype(str).isin(selected_ids)
        if "ticker" in frame:
            keep |= frame["ticker"].astype(str).isin(selected_tickers)
        return frame.loc[keep].copy()

    base = _as_security_frame(bundle.frames.get("final_recommendations", pd.DataFrame()), "final", "final_selected_weight")
    frames = [
        selected(base),
        selected(_as_security_frame(bundle.frames.get("recommendations_portfolio_aware", pd.DataFrame()), "portfolio_aware", rec_col="final_recommendation")),
        selected(_as_security_frame(bundle.frames.get("recommendations_clean_sheet", pd.DataFrame()), "clean_sheet", rec_col="final_recommendation")),
        selected(_as_security_frame(bundle.frames.get("drl_target_weights", pd.DataFrame()), "drl", "target_weight")),
        selected(_as_security_frame(resolved.portfolio, "final", "target_weight")),
        selected(_as_security_frame(bundle.frames.get("llm_benchmark_results", pd.DataFrame()), "llm", rec_col="recommendation")),
    ]
    optimiser = resolved.portfolio.copy()
    optimiser["optimiser_weight"] = pd.to_numeric(optimiser.get("target_weight", optimiser.get("final_weight", 0.0)), errors="coerce").fillna(0.0)
    frames.append(selected(_as_security_frame(optimiser, "optimiser", "optimiser_weight")))
    merged = pd.DataFrame({"security_id": pd.concat([f["security_id"] for f in frames if "security_id" in f], ignore_index=True).dropna().astype(str).unique()})
    for frame in frames:
        merged = merged.merge(frame, on="security_id", how="left", suffixes=("", "_dup"))
        for column in [c for c in merged.columns if c.endswith("_dup")]:
            original = column[:-4]
            if original in merged:
                merged[original] = merged[original].fillna(merged[column])
            merged = merged.drop(columns=[column])
    for column in ["portfolio_aware_recommendation", "clean_sheet_recommendation", "llm_recommendation"]:
        if column not in merged:
            merged[column] = ""
    for column in ["optimiser_weight", "drl_weight", "final_weight"]:
        if column not in merged:
            merged[column] = 0.0
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0.0)
    if "ticker" not in merged:
        merged["ticker"] = merged["security_id"]
    merged["consensus_category"] = merged.apply(_consensus, axis=1)
    merged["disagreement_flag"] = merged["consensus_category"].isin(
        ["Portfolio-Aware Only", "Clean-Sheet Only", "DRL Overweight", "DRL Underweight", "Quant Buy / LLM Caution", "Quant Caution / LLM Buy", "No Consensus"]
    )
    merged["disagreement_commentary"] = merged["consensus_category"].map(lambda value: "LLM is non-authoritative; quant/risk source remains primary." if "LLM" in value else value)
    return merged[
        [
            "security_id",
            "ticker",
            "portfolio_aware_recommendation",
            "clean_sheet_recommendation",
            "optimiser_weight",
            "drl_weight",
            "final_weight",
            "llm_recommendation",
            "consensus_category",
            "disagreement_flag",
            "disagreement_commentary",
        ]
    ]
