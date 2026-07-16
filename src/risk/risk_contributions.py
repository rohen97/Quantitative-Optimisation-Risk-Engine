from __future__ import annotations

import pandas as pd


def build_risk_contribution_report(portfolio: pd.DataFrame) -> pd.DataFrame:
    """Calculate stock-level contributions to return, income and downside risk."""
    data = portfolio.copy()
    weights = data.get("target_weight", pd.Series(0, index=data.index)).fillna(0)
    def series(column: str, default: float) -> pd.Series:
        return data[column].fillna(default) if column in data else pd.Series(default, index=data.index)
    data["contribution_to_expected_return"] = weights * data["expected_total_return_12m"].fillna(0)
    data["contribution_to_dividend_income"] = weights * data["dividend_yield"].fillna(0)
    data["contribution_to_volatility"] = weights * data["expected_volatility_12m"].fillna(0.20)
    data["contribution_to_var_5"] = weights * data["var_5_12m"].fillna(-0.20)
    data["contribution_to_cvar_5"] = weights * data["cvar_5_12m"].fillna(-0.30)
    data["contribution_to_expected_shortfall_5"] = weights * data["expected_shortfall_5_12m"].fillna(-0.30)
    data["contribution_to_drawdown_risk"] = weights * data["large_drawdown_probability_12m"].fillna(0.20)
    data["contribution_to_dividend_cut_risk"] = weights * data["dividend_cut_probability"].fillna(0.10)
    data["contribution_to_tail_risk"] = weights * series("tail_risk_score", 50) / 100
    data["contribution_to_liquidity_risk"] = weights * (100 - series("liquidity_score", 50)) / 100
    data["contribution_to_regime_risk"] = weights * (100 - series("regime_suitability_score", 50)) / 100
    data["contribution_to_narrative_risk"] = weights * series("narrative_reframing_score", 50) / 100
    data["contribution_to_alt_data_risk"] = weights * (100 - series("sentiment_alt_data_score", 50)) / 100
    risk_proxy = (
        data["contribution_to_volatility"].abs()
        + data["contribution_to_cvar_5"].abs()
        + data["contribution_to_expected_shortfall_5"].abs()
        + data["contribution_to_drawdown_risk"].abs()
        + data["contribution_to_tail_risk"].abs()
    )
    data["risk_contribution_rank"] = risk_proxy.rank(ascending=False, method="first").astype(int)
    data["risk_commentary"] = "Low-risk defensive contributor with strong diversification benefit."
    high_cvar = data["contribution_to_cvar_5"].abs() > data["contribution_to_cvar_5"].abs().quantile(0.75)
    data.loc[high_cvar, "risk_commentary"] = "Top contributor to CVaR due to high target weight, elevated volatility and weak downside distribution."
    income = data["contribution_to_dividend_income"] > data["contribution_to_dividend_income"].quantile(0.75)
    data.loc[income & ~high_cvar, "risk_commentary"] = "Moderate risk contributor but strong dividend income contribution."
    narrative = data["contribution_to_narrative_risk"] > data["contribution_to_narrative_risk"].quantile(0.75)
    data.loc[narrative, "risk_commentary"] = "High narrative/regime risk contribution despite attractive yield."
    columns = [
        "security_id",
        "ticker",
        "company_name",
        "target_weight",
        "current_weight",
        "sector",
        "country",
        "region",
        "currency",
        "contribution_to_expected_return",
        "contribution_to_dividend_income",
        "contribution_to_volatility",
        "contribution_to_var_5",
        "contribution_to_cvar_5",
        "contribution_to_expected_shortfall_5",
        "contribution_to_drawdown_risk",
        "contribution_to_dividend_cut_risk",
        "contribution_to_tail_risk",
        "contribution_to_liquidity_risk",
        "contribution_to_regime_risk",
        "contribution_to_narrative_risk",
        "contribution_to_alt_data_risk",
        "risk_contribution_rank",
        "risk_commentary",
    ]
    return data[[col for col in columns if col in data]].sort_values("risk_contribution_rank").reset_index(drop=True)
