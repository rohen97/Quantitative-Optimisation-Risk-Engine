from __future__ import annotations

import json

import pandas as pd

from src.risk.scenario_library import build_scenario_library


def _number(value: object, default: float) -> float:
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _scenario_shock(row: pd.Series, scenario: dict) -> tuple[float, str]:
    if (
        str(row.get("ticker", "")).upper() == "CASH"
        or str(row.get("instrument_type", "")).lower() == "cash"
    ):
        return 0.0, "cash"
    shock = float(scenario.get("base_shock", 0.0))
    drivers = []
    for key, col in [("region_shocks", "region"), ("country_shocks", "country"), ("sector_shocks", "sector"), ("currency_shocks", "currency")]:
        value = scenario.get(key, {}).get(row.get(col), 0.0)
        if value:
            shock += value
            drivers.append(f"{col}:{row.get(col)}")
    if scenario.get("beta_extra") and _number(row.get("beta_local_market"), 1.0) > 1.1:
        shock += scenario["beta_extra"]
        drivers.append("high_beta")
    if scenario.get("liquidity_extra") and _number(row.get("liquidity_score"), 50.0) < 45:
        shock += scenario["liquidity_extra"]
        drivers.append("liquidity")
    if scenario.get("low_quality_extra") and _number(
        row.get("balance_sheet_strength_score"), 50.0
    ) < 45:
        shock += scenario["low_quality_extra"]
        drivers.append("low_quality")
    if scenario.get("regulatory_extra") and _number(
        row.get("regulatory_risk_score"), 0.0
    ) > 60:
        shock += scenario["regulatory_extra"]
        drivers.append("regulatory")
    if scenario.get("debt_extra") and _number(row.get("net_debt_to_ebitda"), 2.0) > 3:
        shock += scenario["debt_extra"]
        drivers.append("high_debt")
    if scenario.get("credit_extra") and _number(row.get("credit_stress_score"), 0.0) > 50:
        shock += scenario["credit_extra"]
        drivers.append("credit_stress")
    if scenario.get("dividend_cut_extra") and _number(
        row.get("dividend_cut_probability"), 0.1
    ) > 0.35:
        shock += scenario["dividend_cut_extra"]
        drivers.append("dividend_cut_probability")
    if scenario.get("payout_extra") and _number(row.get("payout_ratio"), 0.55) > 0.85:
        shock += scenario["payout_extra"]
        drivers.append("high_payout")
    if scenario.get("low_adv_extra") and _number(
        row.get("average_daily_value_usd"), 5_000_000.0
    ) < 5_000_000:
        shock += scenario["low_adv_extra"]
        drivers.append("low_adv")
    if scenario.get("meta_wolf_extra") and "META WOLF" in str(row.get("company_name", "")).upper():
        shock += scenario["meta_wolf_extra"]
        drivers.append("meta_wolf")
    if scenario.get("tail_risk_extra") and _number(row.get("tail_risk_score"), 50.0) > 70:
        shock += scenario["tail_risk_extra"]
        drivers.append("tail_risk")
    return max(shock, -0.85), ";".join(drivers) or "base"


def run_stress_test_contributions(
    portfolio: pd.DataFrame,
    regime_summary: pd.DataFrame | None = None,
    nav_usd: float | None = None,
) -> pd.DataFrame:
    """Run all scenario shocks and return stock-level contribution rows."""
    data = portfolio.copy()
    if "target_weight" not in data:
        if "market_value_usd" in data and data["market_value_usd"].sum() > 0:
            data["target_weight"] = data["market_value_usd"] / data["market_value_usd"].sum()
        else:
            data["target_weight"] = 0.0
    nav = float(nav_usd or data.get("market_value_usd", pd.Series([100_000_000])).sum() or 100_000_000)
    rows = []
    for scenario in build_scenario_library(regime_summary):
        for _, row in data.iterrows():
            shock, driver = _scenario_shock(row, scenario)
            loss_usd = float(row["target_weight"] * nav * shock)
            rows.append(
                {
                    "scenario_name": scenario["scenario_name"],
                    "security_id": row.get("security_id", ""),
                    "ticker": row.get("ticker", ""),
                    "company_name": row.get("company_name", ""),
                    "sector": row.get("sector", ""),
                    "country": row.get("country", ""),
                    "region": row.get("region", ""),
                    "currency": row.get("currency", ""),
                    "target_weight": row.get("target_weight", 0),
                    "shock_pct": shock,
                    "position_loss_pct": row.get("target_weight", 0) * shock,
                    "position_loss_usd": loss_usd,
                    "contribution_to_portfolio_loss": row.get("target_weight", 0) * shock,
                    "stress_driver": driver,
                }
            )
    return pd.DataFrame(rows)


def build_stress_test_report(contributions: pd.DataFrame, nav_usd: float = 100_000_000) -> pd.DataFrame:
    """Aggregate stock-level stress contributions into scenario-level report."""
    rows = []
    for scenario, frame in contributions.groupby("scenario_name"):
        loss_pct = float(frame["contribution_to_portfolio_loss"].sum())
        loss_usd = float(frame["position_loss_usd"].sum())
        top = frame.sort_values("position_loss_usd").head(5)
        sector = frame.groupby("sector")["position_loss_usd"].sum().sort_values().to_dict()
        country = frame.groupby("country")["position_loss_usd"].sum().sort_values().to_dict()
        currency = frame.groupby("currency")["position_loss_usd"].sum().sort_values().to_dict()
        rows.append(
            {
                "scenario_name": scenario,
                "portfolio_loss_pct": loss_pct,
                "portfolio_loss_usd": loss_usd,
                "post_stress_portfolio_value": nav_usd + loss_usd,
                "post_stress_var_5": loss_pct * 0.85,
                "post_stress_cvar_5": loss_pct * 1.10,
                "post_stress_expected_shortfall_5": loss_pct * 1.15,
                "post_stress_dividend_income_impact": min(loss_pct * 0.25, 0),
                "post_stress_drawdown_probability": min(max(abs(loss_pct) * 2.2, 0), 1),
                "top_5_loss_contributors": ", ".join(top["ticker"].astype(str)),
                "sector_loss_contribution": json.dumps(sector, sort_keys=True),
                "country_loss_contribution": json.dumps(country, sort_keys=True),
                "currency_loss_contribution": json.dumps(currency, sort_keys=True),
                "risk_level": "Severe" if loss_pct < -0.20 else "High" if loss_pct < -0.10 else "Moderate",
                "hedge_required_flag": loss_pct < -0.10,
                "stress_commentary": "Stress scenario estimates deterministic mock portfolio loss and main loss contributors.",
            }
        )
    return pd.DataFrame(rows).sort_values("portfolio_loss_pct").reset_index(drop=True)


def run_stress_tests(
    portfolio: pd.DataFrame,
    regime_summary: pd.DataFrame | None = None,
    return_contributions: bool = False,
    nav_usd: float | None = None,
):
    contributions = run_stress_test_contributions(portfolio, regime_summary, nav_usd)
    report = build_stress_test_report(contributions, nav_usd or 100_000_000)
    return (report, contributions) if return_contributions else report
