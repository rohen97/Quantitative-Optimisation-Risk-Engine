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
    "optimised_portfolio_regional_alpha": "optimised_portfolio_regional_alpha",
    "optimised_portfolio_dividend_income": "optimised_portfolio_dividend_income",
    "optimised_portfolio_regime_aware": "optimised_portfolio_regime_aware",
}


class PortfolioFeasibilityError(RuntimeError):
    """Carries the exact failed optimiser evidence for durable diagnostics."""

    def __init__(
        self,
        message: str,
        optimiser_inputs: pd.DataFrame,
        summary: pd.DataFrame,
        constraint_report: pd.DataFrame,
    ) -> None:
        super().__init__(message)
        self.optimiser_inputs = optimiser_inputs
        self.summary = summary
        self.constraint_report = constraint_report


def build_final_portfolio_weights(
    final_recommendations: pd.DataFrame,
    optimiser_inputs: pd.DataFrame,
) -> pd.DataFrame:
    """Build the compact authoritative portfolio selected after the DRL gate."""
    if final_recommendations.empty or "final_selected_weight" not in final_recommendations:
        return pd.DataFrame()
    selected = final_recommendations.copy()
    selected["target_weight"] = pd.to_numeric(
        selected["final_selected_weight"],
        errors="coerce",
    ).fillna(0.0)
    selected = selected.loc[selected["target_weight"].gt(1e-12)].copy()
    if selected.empty:
        return selected
    metadata_columns = [
        column
        for column in [
            "security_id",
            "ticker",
            "issuer_id",
            "company_name",
            "country",
            "region",
            "sector",
            "industry",
            "currency",
            "average_daily_value_usd",
            "market_cap_usd",
            "dividend_yield",
            "expected_total_return_12m",
            "expected_dividend_return_12m",
            "expected_volatility_12m",
            "p5_return_12m",
            "p50_return_12m",
            "p95_return_12m",
            "var_5_12m",
            "cvar_5_12m",
            "expected_shortfall_5_12m",
            "dividend_cut_probability",
            "large_drawdown_probability_12m",
            "regime_suitability_score",
            "sector_data_source",
            "liquidity_data_source",
            "market_cap_data_source",
            "fundamentals_data_source",
            "is_synthetic_data",
            "is_synthetic_fundamentals",
            "price_data_quality_score",
            "price_data_exclusion_flag",
            "eligible_for_optimisation",
            "fallback_eligibility_used",
            "optimisation_feasible",
            "optimisation_status",
            "portfolio_method",
        ]
        if column in optimiser_inputs
    ]
    metadata = optimiser_inputs[metadata_columns].drop_duplicates("ticker")
    overlapping = [column for column in metadata.columns if column != "ticker" and column in selected]
    selected = selected.drop(columns=overlapping, errors="ignore").merge(metadata, on="ticker", how="left")
    selected["final_weight"] = selected["target_weight"]
    allocated = float(selected["target_weight"].sum())
    if allocated < 1.0 - 1e-8:
        cash = {column: pd.NA for column in selected.columns}
        cash.update(
            {
                "security_id": "CASH",
                "ticker": "CASH",
                "company_name": "Cash",
                "country": "Cash",
                "region": "Cash",
                "sector": "Cash",
                "industry": "Cash",
                "currency": "USD",
                "target_weight": 1.0 - allocated,
                "final_weight": 1.0 - allocated,
                "portfolio_method": "cash_residual",
            }
        )
        selected = pd.concat([selected, pd.DataFrame([cash])], ignore_index=True)
    selected = selected.sort_values(["target_weight", "ticker"], ascending=[False, True]).reset_index(drop=True)
    if not selected["ticker"].is_unique:
        raise RuntimeError("Final portfolio contains duplicate ticker rows.")
    if "issuer_id" in selected and selected["issuer_id"].dropna().duplicated().any():
        raise RuntimeError("Final portfolio contains duplicate issuer allocations.")
    if not abs(float(selected["target_weight"].sum()) - 1.0) <= 1e-8:
        raise RuntimeError("Final selected portfolio weights do not sum to one.")
    return selected


def _nav(current: pd.DataFrame | None, fallback: float) -> float:
    if current is not None and not current.empty and "market_value_usd" in current:
        total = float(current["market_value_usd"].sum())
        return total if total > 0 else fallback
    return fallback


def _selected_method(summary: pd.DataFrame) -> str:
    preference = ["cvar_constrained", "regime_aware", "score_weighted", "equal_weight"]
    breach_free = summary["hard_constraint_breaches"].fillna(1).eq(0)
    solver_feasible = summary["optimisation_feasible"].fillna(False).astype(bool)
    feasible = summary[breach_free & solver_feasible]
    if feasible.empty:
        raise RuntimeError(
            "No feasible optimiser portfolio satisfies all hard constraints. "
            "Review optimiser_input_dataset.csv and portfolio_constraint_report.csv."
        )
    methods = set(feasible["portfolio_method"])
    for method in preference:
        if method in methods:
            return method
    return str(feasible["portfolio_method"].iloc[0])


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
    constraint_reports = []
    for key, frame in portfolios.items():
        method = frame["portfolio_method"].iloc[0] if not frame.empty else key.replace("optimised_portfolio_", "")
        metrics = summarise_portfolio_metrics(frame, nav_usd, method)
        report = build_constraint_report(frame, constraints)
        report.insert(0, "portfolio_method", method)
        constraint_reports.append(report)
        hard_breaches = int(report.loc[(report["constraint_type"].eq("hard")) & (report["breach_flag"]), "breach_flag"].sum())
        soft_breaches = int(report.loc[(report["constraint_type"].eq("soft")) & (report["breach_flag"]), "breach_flag"].sum())
        metrics["constraint_breaches"] = f"hard={hard_breaches};soft={soft_breaches}"
        metrics["hard_constraint_breaches"] = hard_breaches
        metrics["soft_constraint_breaches"] = soft_breaches
        metrics["optimisation_feasible"] = bool(
            not frame.empty
            and frame.get("optimisation_feasible", pd.Series(False, index=frame.index)).fillna(False).all()
        )
        metrics["optimisation_status"] = (
            str(frame["optimisation_status"].iloc[0])
            if not frame.empty and "optimisation_status" in frame
            else "missing"
        )
        metrics["eligible_security_count"] = (
            int(frame["eligible_security_count"].iloc[0])
            if not frame.empty and "eligible_security_count" in frame
            else 0
        )
        metrics["candidate_security_count"] = (
            int(frame["candidate_security_count"].iloc[0])
            if not frame.empty and "candidate_security_count" in frame
            else 0
        )
        metrics["selected_recommended_portfolio"] = False
        summary_rows.append(metrics)
    summary = pd.DataFrame(summary_rows)
    combined_constraints = (
        pd.concat(constraint_reports, ignore_index=True)
        if constraint_reports
        else pd.DataFrame()
    )
    try:
        selected = _selected_method(summary) if not summary.empty else "equal_weight"
    except RuntimeError as exc:
        raise PortfolioFeasibilityError(
            str(exc),
            inputs,
            summary,
            combined_constraints,
        ) from exc
    summary.loc[summary["portfolio_method"].eq(selected), "selected_recommended_portfolio"] = True
    selected_key = next((key for key, frame in portfolios.items() if not frame.empty and frame["portfolio_method"].iloc[0] == selected), None)
    if selected_key is None:
        raise RuntimeError(f"Selected optimiser method {selected!r} has no portfolio output.")
    selected_portfolio = portfolios[selected_key]
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


def build_proposed_portfolio(
    current: pd.DataFrame,
    recommendations: pd.DataFrame,
    max_new_names: int = 8,
    max_single_name_weight: float = 0.05,
) -> pd.DataFrame:
    buys = recommendations[recommendations["target_weight"] > 0].head(max_new_names)
    proposed = buys[["ticker", "company_name", "sector", "country", "currency", "target_weight", "recommendation"]].copy()
    proposed["target_weight"] = proposed["target_weight"].clip(upper=max_single_name_weight)
    if proposed["target_weight"].sum() > 0.35:
        proposed["target_weight"] *= 0.35 / proposed["target_weight"].sum()
    return proposed
