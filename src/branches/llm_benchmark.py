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
        + 0.15 * data.get("sentiment_alt_data_score", data["sentiment_alt_signal_score"]).fillna(0)
        - 0.10 * data.get("event_severity_score", pd.Series(0, index=data.index)).fillna(0)
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
    improving_narrative = data.get("positive_reframing_score", pd.Series(0, index=data.index)).fillna(0) > 75
    data.loc[improving_narrative, "investment_thesis"] += " Narrative is improving toward quality, growth and capital return."
    regime = data.get("dominant_regime", pd.Series("steady_state_low_chaos", index=data.index)).fillna("steady_state_low_chaos")
    regime_risk = data.get("regime_risk_score", pd.Series(50, index=data.index)).fillna(50)
    data["investment_thesis"] += " Current regime lens: " + regime.astype(str) + "."
    dividend_risk = data.get("dividend_risk_score", pd.Series(0, index=data.index)).fillna(0) > 80
    regulatory_risk = data.get("regulatory_risk_score", pd.Series(0, index=data.index)).fillna(0) > 75
    credit_risk = data.get("credit_stress_score", pd.Series(0, index=data.index)).fillna(0) > 75
    data["key_risks"] = "Mock risks: valuation compression, policy/regulatory shocks, dividend sustainability and liquidity stress."
    data.loc[dividend_risk, "key_risks"] += " Dividend sustainability risk is elevated."
    data.loc[regulatory_risk, "key_risks"] += " Regulatory overhang is elevated."
    data.loc[credit_risk, "key_risks"] += " Credit stress risk is elevated."
    risk_reframing = data.get("risk_reframing_score", pd.Series(0, index=data.index)).fillna(0) > 80
    dividend_reframing = data.get("dividend_risk_similarity_score", pd.Series(0, index=data.index)).fillna(0) > 85
    credit_reframing = data.get("credit_stress_similarity_score", pd.Series(0, index=data.index)).fillna(0) > 85
    data.loc[risk_reframing, "key_risks"] += " Narrative is reframing toward risk/deterioration."
    data.loc[dividend_reframing, "key_risks"] += " Dividend story is shifting toward sustainability concerns."
    data.loc[credit_reframing, "key_risks"] += " Credit/refinancing pressure is increasingly central to the equity story."
    data.loc[regime_risk > 70, "key_risks"] += " Market-state risk is elevated under the fused regime model."
    data.loc[data.get("regime_review_required_flag", pd.Series(False, index=data.index)).astype(bool), "key_risks"] += " Regime suitability requires review."
    expected_return = data.get("expected_total_return_12m", pd.Series(0, index=data.index)).fillna(0)
    p5_return = data.get("p5_return_12m", pd.Series(0, index=data.index)).fillna(0)
    dividend_cut_probability = data.get("dividend_cut_probability", pd.Series(0, index=data.index)).fillna(0)
    forecast_uncertainty = data.get("forecast_uncertainty_score", pd.Series(50, index=data.index)).fillna(50)
    ml_score = data.get("ml_expected_risk_adjusted_score", pd.Series(50, index=data.index)).fillna(50)
    var_5 = data.get("var_5_12m", pd.Series(-0.10, index=data.index)).fillna(-0.10)
    cvar_5 = data.get("cvar_5_12m", pd.Series(-0.12, index=data.index)).fillna(-0.12)
    nu = data.get("distribution_nu_12m", pd.Series(8, index=data.index)).fillna(8)
    skewness_risk = data.get("skewness_risk_score", pd.Series(50, index=data.index)).fillna(50)
    distribution_confidence = data.get("distribution_model_confidence", pd.Series(70, index=data.index)).fillna(70)
    data.loc[(expected_return > 0.12) & ((p5_return < -0.20) | (var_5 < -0.20) | (cvar_5 < -0.25)), "key_risks"] += (
        " Distributional ML forecast shows attractive upside but asymmetric downside risk."
    )
    data.loc[dividend_cut_probability > 0.35, "key_risks"] += " ML dividend-cut probability is elevated."
    data.loc[forecast_uncertainty > 75, "key_risks"] += " Forecast uncertainty is high; analyst placeholder treats this as Watchlist risk."
    data.loc[nu < 4, "key_risks"] += " Forecast distribution has fat-tail risk."
    data.loc[skewness_risk > 75, "key_risks"] += " Forecast distribution has downside skew risk."
    data.loc[distribution_confidence < 45, "key_risks"] += " Distribution model confidence is low."
    data.loc[(ml_score > 65) & (data["final_recommendation_score"] > 65), "investment_thesis"] += " ML forecast and quant score are aligned."
    data.loc[forecast_uncertainty > 75, "llm_recommendation"] = np.where(data.loc[forecast_uncertainty > 75, "llm_recommendation"].eq("Buy"), "Hold", data.loc[forecast_uncertainty > 75, "llm_recommendation"])
    data.loc[distribution_confidence < 45, "llm_recommendation"] = np.where(
        data.loc[distribution_confidence < 45, "llm_recommendation"].eq("Buy"),
        "Hold",
        data.loc[distribution_confidence < 45, "llm_recommendation"],
    )
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
