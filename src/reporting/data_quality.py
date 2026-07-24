from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.reporting.models import ICDataBundle


REQUIRED_FRAMES = (
    "current_portfolio",
    "final_recommendations",
    "risk_report",
    "stress_report",
    "regime_summary",
    "model_run_lineage",
)


def build_data_quality_report(bundle: ICDataBundle) -> pd.DataFrame:
    rows = []
    root = bundle.source_root or Path("reports/outputs")
    for name in REQUIRED_FRAMES:
        frame = bundle.frames.get(name, pd.DataFrame())
        path = root / f"{name}.csv"
        rows.append(
            {
                "dataset": name,
                "available": not frame.empty,
                "row_count": len(frame),
                "freshness_checked": path.exists(),
                "file_path": str(path),
                "status": "pass" if not frame.empty else "missing_or_empty",
            }
        )
    return pd.DataFrame(rows)


def build_report_data_quality(bundle: ICDataBundle, final_portfolio: pd.DataFrame, as_of_date: pd.Timestamp) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    def add(section: str, rule: str, status: str, message: str) -> None:
        rows.append({"section": section, "rule": rule, "status": status, "message": message})

    if final_portfolio.empty:
        add("portfolio", "target_portfolio_available", "fail", "No target portfolio is available.")
    else:
        add("portfolio", "target_portfolio_available", "pass", "Target portfolio is available.")
        weights = pd.to_numeric(final_portfolio.get("target_weight", final_portfolio.get("final_weight", pd.Series(dtype=float))), errors="coerce")
        add("portfolio", "security_ids_present", "pass" if "security_id" in final_portfolio else "fail", "Security IDs are required.")
        add("portfolio", "unique_holdings", "pass" if "security_id" in final_portfolio and final_portfolio["security_id"].is_unique else "fail", "Holdings must be unique by security_id.")
        add("portfolio", "finite_weights", "pass" if weights.notna().all() and np.isfinite(weights).all() else "fail", "Weights must be finite.")
        add("portfolio", "long_only", "pass" if (weights >= -1e-10).all() else "fail", "Long-only portfolio cannot have negative weights.")
        add("portfolio", "weights_sum_to_one", "pass" if np.isclose(weights.sum(), 1.0, atol=1e-5) else "fail", f"Weights sum to {weights.sum():.6f}.")
    current = bundle.frames.get("current_portfolio", pd.DataFrame())
    nav = pd.to_numeric(current.get("market_value_usd", pd.Series(dtype=float)), errors="coerce").sum() if not current.empty else 0.0
    add("portfolio", "current_nav_positive", "pass" if nav > 0 else "warning", "Current NAV should be positive when current portfolio is available.")

    forecasts = pd.concat([bundle.frames.get(f"ml_forecasts_{h}m", pd.DataFrame()) for h in (3, 6, 9, 12)], ignore_index=True)
    if forecasts.empty:
        add("forecasts", "forecast_section_available", "warning", "Forecast section is unavailable.")
    else:
        for column in ("expected_total_return", "p5_return", "p50_return", "p95_return"):
            if column in forecasts:
                values = pd.to_numeric(forecasts[column], errors="coerce")
                add("forecasts", f"{column}_finite", "pass" if values.notna().all() else "fail", f"{column} must be finite.")
        if {"p5_return", "p50_return", "p95_return"}.issubset(forecasts.columns):
            p5 = pd.to_numeric(forecasts["p5_return"], errors="coerce")
            p50 = pd.to_numeric(forecasts["p50_return"], errors="coerce")
            p95 = pd.to_numeric(forecasts["p95_return"], errors="coerce")
            add("forecasts", "quantile_order", "pass" if ((p5 <= p50) & (p50 <= p95)).all() else "fail", "Forecast quantiles require P5 <= P50 <= P95.")
        for column in ("dividend_cut_probability", "large_drawdown_probability"):
            if column in forecasts:
                values = pd.to_numeric(forecasts[column], errors="coerce")
                add("forecasts", f"{column}_bounds", "pass" if values.between(0, 1).all() else "fail", f"{column} must be between 0 and 1.")

    risk = bundle.frames.get("risk_report", pd.DataFrame())
    if risk.empty:
        add("risk", "risk_report_available", "fail", "Portfolio risk report is unavailable.")
    elif {"portfolio_var_5", "portfolio_expected_shortfall_5"}.issubset(risk.columns):
        var = pd.to_numeric(risk["portfolio_var_5"], errors="coerce")
        es = pd.to_numeric(risk["portfolio_expected_shortfall_5"], errors="coerce")
        add("risk", "expected_shortfall_vs_var", "pass" if (es <= var).all() else "fail", "Expected Shortfall should be at least as severe as VaR under negative-loss convention.")

    stress = bundle.frames.get("stress_report", pd.DataFrame())
    if not stress.empty and "scenario_name" in stress:
        add("stress", "scenario_names_unique", "pass" if stress["scenario_name"].is_unique else "fail", "Stress scenario names must be unique.")
    if not stress.empty and "portfolio_loss_pct" in stress:
        losses = pd.to_numeric(stress["portfolio_loss_pct"], errors="coerce")
        add("stress", "loss_sign_convention", "pass" if (losses <= 0).all() else "warning", "Stress losses should use negative-loss convention.")

    regime = bundle.frames.get("chaos_regime_probabilities", pd.DataFrame())
    if not regime.empty:
        probability_columns = [
            column for column in regime.columns if "probability" in str(column).lower()
        ]
        probabilities = regime[probability_columns].apply(pd.to_numeric, errors="coerce")
        if not probabilities.empty:
            valid = probabilities.notna().all().all() and probabilities.stack().between(0, 1).all()
            add("regime", "probability_bounds", "pass" if valid else "fail", "Regime probabilities must be between 0 and 1.")

    drl_acceptance = bundle.frames.get("drl_acceptance", pd.DataFrame())
    drl_weights = bundle.frames.get("drl_target_weights", pd.DataFrame())
    if not drl_acceptance.empty and not drl_weights.empty:
        add("drl", "seed_results_available", "pass" if not bundle.frames.get("drl_seed_results", pd.DataFrame()).empty else "warning", "Seed results should be available when DRL is active.")
    add("lineage", "model_run_id_present", "pass" if bool(bundle.model_run_id) else "fail", "Model run ID must be present.")

    return pd.DataFrame(rows)


def report_is_valid(quality: pd.DataFrame) -> bool:
    return not quality.empty and quality["status"].eq("pass").all()
