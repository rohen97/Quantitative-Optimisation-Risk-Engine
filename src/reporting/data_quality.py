from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.reporting.models import ICDataBundle
from src.utils.config import ROOT


REQUIRED_FRAMES = (
    "current_portfolio",
    "final_portfolio_weights",
    "final_recommendations",
    "risk_report",
    "stress_report",
    "regime_summary",
    "model_run_lineage",
)


def _portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


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
                "file_path": _portable_path(path),
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
        if "issuer_id" in final_portfolio:
            issuer = final_portfolio["issuer_id"].dropna().astype(str)
            add(
                "portfolio",
                "unique_issuers",
                "pass" if issuer.is_unique else "fail",
                "Cross-listed securities must not create duplicate issuer exposure.",
            )
        for column in ("sector", "country", "region", "currency"):
            if column not in final_portfolio:
                add("data_provenance", f"{column}_available", "fail", f"{column} metadata is required.")
                continue
            values = final_portfolio[column].fillna("Unknown").astype(str).str.strip().str.lower()
            known = ~values.isin({"", "unknown", "nan", "none", "n/a", "<na>"})
            add(
                "data_provenance",
                f"{column}_known",
                "pass" if known.all() else "fail",
                f"Every selected holding requires known {column} metadata.",
            )
        recommendation = final_portfolio.get(
            "final_recommendation",
            pd.Series("", index=final_portfolio.index),
        ).fillna("").astype(str)
        prohibited = recommendation.str.contains("avoid|exclude", case=False, regex=True)
        add(
            "portfolio",
            "selected_names_are_investable",
            "pass" if not prohibited.any() else "fail",
            "Selected holdings cannot carry Avoid or Exclude recommendations.",
        )
        synthetic = (
            final_portfolio.get("is_synthetic_data", pd.Series(False, index=final_portfolio.index))
            .fillna(False)
            .astype(bool)
            | final_portfolio.get(
                "is_synthetic_fundamentals",
                pd.Series(False, index=final_portfolio.index),
            )
            .fillna(False)
            .astype(bool)
        )
        add(
            "data_provenance",
            "observed_investment_inputs",
            "pass" if not synthetic.any() else "fail",
            "Synthetic metadata or fundamentals are allowed for testing but block deployment.",
        )
        fallback = final_portfolio.get(
            "fallback_eligibility_used",
            pd.Series(False, index=final_portfolio.index),
        ).fillna(False).astype(bool)
        add(
            "portfolio",
            "hard_eligibility_not_bypassed",
            "pass" if not fallback.any() else "fail",
            "Final holdings must come from the strict hard-eligibility set.",
        )
        feasible = final_portfolio.get(
            "optimisation_feasible",
            pd.Series(False, index=final_portfolio.index),
        ).fillna(False).astype(bool)
        add(
            "portfolio",
            "optimiser_feasible",
            "pass" if feasible.all() else "fail",
            "The selected optimiser must report a feasible hard-constraint solution.",
        )
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
