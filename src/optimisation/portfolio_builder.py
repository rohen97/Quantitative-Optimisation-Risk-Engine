from __future__ import annotations

import pandas as pd

from src.optimisation.constraint_report import build_constraint_report
from src.optimisation.optimiser_inputs import build_optimiser_input_dataset
from src.optimisation.optimisers import run_all_optimisers
from src.optimisation.portfolio_math import summarise_portfolio_metrics
from src.optimisation.trade_list import build_trade_list


OUTPUT_NAME_MAP = {
    "optimised_portfolio_score_weighted": "optimised_portfolio_score_weighted",
    "optimised_portfolio_risk_parity": "optimised_portfolio_risk_parity",
    "optimised_portfolio_mean_variance": "optimised_portfolio_mean_variance",
    "optimised_portfolio_cvar_constrained": "optimised_portfolio_cvar_constrained",
    "optimised_portfolio_dividend_income": "optimised_portfolio_dividend_income",
    "optimised_portfolio_regime_aware": "optimised_portfolio_regime_aware",
}


def _nav(current: pd.DataFrame | None, fallback: float) -> float:
    if current is not None and not current.empty and "market_value_usd" in current:
        total = float(current["market_value_usd"].sum())
        return total if total > 0 else fallback
    return fallback


def _selected_method(summary: pd.DataFrame) -> str:
    preference = ["cvar_constrained", "regime_aware", "score_weighted", "equal_weight"]
    feasible = summary[~summary["constraint_breaches"].astype(str).str.contains("hard", case=False, na=False)]
    methods = set(feasible["portfolio_method"]) if not feasible.empty else set(summary["portfolio_method"])
    for method in preference:
        if method in methods:
            return method
    return str(summary["portfolio_method"].iloc[0])


def run_portfolio_optimisation(
    scorecard: pd.DataFrame,
    current_portfolio: pd.DataFrame,
    optimisation_config: dict | None = None,
    final_recommendations: pd.DataFrame | None = None,
    regime_dashboard: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    """Run all portfolio constructors, summaries, constraint report and trade list."""
    config = (optimisation_config or {}).get("optimisation", optimisation_config or {})
    constraints = config.get("constraints", {})
    nav_usd = _nav(current_portfolio, config.get("trade_list", {}).get("portfolio_nav_usd_fallback", 100_000_000))
    dominant_regime = "steady_state_low_chaos"
    if regime_dashboard is not None and not regime_dashboard.empty and "dominant_regime" in regime_dashboard:
        dominant_regime = str(regime_dashboard.iloc[0]["dominant_regime"])
    inputs = build_optimiser_input_dataset(scorecard, current_portfolio, final_recommendations)
    portfolios = run_all_optimisers(inputs, config, dominant_regime)
    summary_rows = []
    for key, frame in portfolios.items():
        method = frame["portfolio_method"].iloc[0] if not frame.empty else key.replace("optimised_portfolio_", "")
        metrics = summarise_portfolio_metrics(frame, nav_usd, method)
        report = build_constraint_report(frame, constraints)
        hard_breaches = int(report.loc[(report["constraint_type"].eq("hard")) & (report["breach_flag"]), "breach_flag"].sum())
        soft_breaches = int(report.loc[(report["constraint_type"].eq("soft")) & (report["breach_flag"]), "breach_flag"].sum())
        metrics["constraint_breaches"] = f"hard={hard_breaches};soft={soft_breaches}"
        metrics["selected_recommended_portfolio"] = False
        summary_rows.append(metrics)
    summary = pd.DataFrame(summary_rows)
    selected = _selected_method(summary) if not summary.empty else "equal_weight"
    summary.loc[summary["portfolio_method"].eq(selected), "selected_recommended_portfolio"] = True
    selected_key = next((key for key, frame in portfolios.items() if not frame.empty and frame["portfolio_method"].iloc[0] == selected), None)
    selected_portfolio = portfolios[selected_key] if selected_key else next(iter(portfolios.values()))
    trade_threshold = config.get("trade_list", {}).get("min_trade_weight_threshold", 0.0025)
    trade_list = build_trade_list(selected_portfolio, nav_usd, trade_threshold)
    constraint_report = build_constraint_report(selected_portfolio, constraints)
    output = {
        "optimiser_input_dataset": inputs,
        "portfolio_optimisation_summary": summary,
        "portfolio_trade_list": trade_list,
        "portfolio_constraint_report": constraint_report,
        "recommended_optimised_portfolio": selected_portfolio,
    }
    output.update({key: frame for key, frame in portfolios.items() if key in OUTPUT_NAME_MAP or key == "optimised_portfolio_equal_weight"})
    return output


def build_proposed_portfolio(current: pd.DataFrame, recommendations: pd.DataFrame, max_new_names: int = 8) -> pd.DataFrame:
    buys = recommendations[recommendations["target_weight"] > 0].head(max_new_names)
    proposed = buys[["ticker", "company_name", "sector", "country", "currency", "target_weight", "recommendation"]].copy()
    if proposed["target_weight"].sum() > 0.35:
        proposed["target_weight"] *= 0.35 / proposed["target_weight"].sum()
    return proposed
