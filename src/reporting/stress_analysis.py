from __future__ import annotations

import pandas as pd

from src.reporting.models import ICDataBundle


def worst_stress_scenarios(bundle: ICDataBundle, n: int = 5) -> pd.DataFrame:
    stress = bundle.frames.get("stress_report", pd.DataFrame()).copy()
    if stress.empty or "portfolio_loss_pct" not in stress:
        return stress.head(n)
    stress["portfolio_loss_pct"] = pd.to_numeric(stress["portfolio_loss_pct"], errors="coerce")
    return stress.sort_values("portfolio_loss_pct").head(n)


REQUIRED_SCENARIOS = (
    "Global risk-off",
    "Crisis / high-chaos",
    "Europe recession",
    "China policy stress",
    "UK rate shock",
    "Inflation shock",
    "Credit stress",
    "Dividend-cut shock",
    "Liquidity shock",
    "Meta Wolf -25%",
    "Meta Wolf -40%",
    "FX shock",
    "Correlation spike",
)


def build_stress_scenario_summary(bundle: ICDataBundle) -> pd.DataFrame:
    stress = bundle.frames.get("stress_report", pd.DataFrame()).copy()
    if stress.empty:
        return pd.DataFrame()
    aliases = {
        "portfolio_loss_pct": "portfolio_loss_percentage",
        "post_stress_portfolio_value": "post_stress_value",
        "post_stress_dividend_income_impact": "post_stress_dividend_impact",
        "risk_level": "risk_severity",
    }
    for source, target in aliases.items():
        if source in stress and target not in stress:
            stress[target] = stress[source]
    if "portfolio_loss_usd" not in stress:
        stress["portfolio_loss_usd"] = pd.NA
    if "top_contributors" not in stress:
        stress["top_contributors"] = stress.get("top_5_loss_contributors", "")
    if "hedge_required_flag" not in stress:
        stress["hedge_required_flag"] = False
    stress["required_scenario_available"] = stress.get("scenario_name", pd.Series(dtype=str)).astype(str).isin(REQUIRED_SCENARIOS)
    required = [
        "scenario_name",
        "portfolio_loss_percentage",
        "portfolio_loss_usd",
        "top_contributors",
        "risk_severity",
        "hedge_required_flag",
        "post_stress_value",
        "post_stress_dividend_impact",
        "required_scenario_available",
    ]
    for column in required:
        if column not in stress:
            stress[column] = pd.NA
    stress["portfolio_loss_percentage"] = pd.to_numeric(stress["portfolio_loss_percentage"], errors="coerce")
    return stress[required].sort_values("portfolio_loss_percentage").reset_index(drop=True)
