from __future__ import annotations

import numpy as np
import pandas as pd

from src.reporting.column_resolver import resolve_column
from src.reporting.models import ICDataBundle
from src.reporting.portfolio_resolver import ResolvedPortfolio, resolve_final_portfolio_from_bundle


def weighted_average(data: pd.DataFrame, value_column: str, weight_column: str) -> float | None:
    if data.empty or value_column not in data or weight_column not in data:
        return None
    values = pd.to_numeric(data[value_column], errors="coerce")
    weights = pd.to_numeric(data[weight_column], errors="coerce")
    valid = values.notna() & weights.notna()
    if not valid.any():
        return None
    valid_weights = weights.loc[valid]
    total_weight = valid_weights.sum()
    if total_weight <= 0:
        return None
    return float(np.average(values.loc[valid], weights=valid_weights))


def _first_numeric(frame: pd.DataFrame, candidates: tuple[str, ...]) -> float | None:
    if frame.empty:
        return None
    for column in candidates:
        if column in frame:
            value = pd.to_numeric(frame[column], errors="coerce").dropna()
            if not value.empty:
                return float(value.iloc[-1])
    return None


def _readiness(
    bundle: ICDataBundle,
    resolved: ResolvedPortfolio | None,
    hard_breaches: int,
    pdf_available: bool = True,
    report_quality: pd.DataFrame | None = None,
) -> str:
    if resolved is None or resolved.portfolio.empty:
        return "BLOCKED"
    weights = pd.to_numeric(resolved.portfolio.get("target_weight", resolved.portfolio.get("final_weight", pd.Series(dtype=float))), errors="coerce")
    if weights.empty or weights.isna().any() or not np.isclose(weights.sum(), 1.0, atol=1e-5):
        return "BLOCKED"
    if hard_breaches > 0:
        return "BLOCKED"
    if report_quality is not None and not report_quality.empty:
        statuses = report_quality.get("status", pd.Series(dtype=str)).astype(str).str.lower()
        if statuses.eq("fail").any():
            return "BLOCKED"
    data_validation = bundle.frames.get("data_validation_report", pd.DataFrame())
    if not data_validation.empty and data_validation.astype(str).apply(lambda col: col.str.contains("fail|error", case=False, na=False)).any().any():
        return "BLOCKED"
    stress = bundle.frames.get("stress_report", pd.DataFrame())
    worst_loss = _first_numeric(stress.sort_values("portfolio_loss_pct") if "portfolio_loss_pct" in stress else stress, ("portfolio_loss_pct", "loss_pct"))
    regime = bundle.frames.get("regime_summary", pd.DataFrame())
    dominant = str(regime.iloc[-1].get("dominant_regime", "")).lower() if not regime.empty else ""
    missing_critical = bundle.frames.get("risk_report", pd.DataFrame()).empty or bundle.frames.get("stress_report", pd.DataFrame()).empty
    hhi = float(np.square(weights).sum())
    drl = bundle.frames.get("drl_acceptance", pd.DataFrame())
    drl_text = " ".join(drl.iloc[-1].astype(str).tolist()).lower() if not drl.empty else ""
    if (
        (worst_loss is not None and worst_loss <= -0.25)
        or "crisis" in dominant
        or "high_chaos" in dominant
        or missing_critical
        or hhi > 0.20
        or ("rejected" in drl_text and "instability" in drl_text)
    ):
        return "REVIEW_REQUIRED"
    missing_optional = any(source.warning for source in bundle.sources if source.name in {"llm_benchmark_results", "regime_informational_drivers"})
    if missing_optional or not pdf_available or resolved.fallback_used:
        return "READY_WITH_WARNINGS"
    return "READY"


def build_executive_summary(
    bundle: ICDataBundle,
    resolved: ResolvedPortfolio | None = None,
    pdf_available: bool = True,
    report_quality: pd.DataFrame | None = None,
) -> dict[str, object]:
    try:
        resolved = resolved or resolve_final_portfolio_from_bundle(bundle)
    except RuntimeError:
        resolved = None
    final_portfolio = resolved.portfolio if resolved is not None else pd.DataFrame()
    current = bundle.frames.get("current_portfolio", pd.DataFrame())
    risk = bundle.frames.get("risk_report", pd.DataFrame())
    regime = bundle.frames.get("regime_summary", pd.DataFrame())
    stress = bundle.frames.get("stress_report", pd.DataFrame())
    drl = bundle.frames.get("drl_acceptance", pd.DataFrame())
    constraints = bundle.frames.get("portfolio_constraint_report", pd.DataFrame())
    hard_breaches = 0
    if not constraints.empty:
        breach_columns = [column for column in constraints.columns if "breach" in str(column).lower() or "violation" in str(column).lower()]
        hard_mask = (
            constraints["constraint_type"].astype(str).str.lower().eq("hard")
            if "constraint_type" in constraints
            else pd.Series(True, index=constraints.index)
        )
        for column in breach_columns:
            raw = constraints[column]
            numeric = pd.to_numeric(raw, errors="coerce")
            parsed = numeric.fillna(0).ne(0)
            text_mask = numeric.isna()
            parsed.loc[text_mask] = raw.loc[text_mask].astype(str).str.strip().str.lower().isin(
                {"true", "yes", "y", "1", "breach", "failed"}
            )
            hard_breaches += int((parsed & hard_mask).sum())
    weights = pd.to_numeric(final_portfolio.get("target_weight", final_portfolio.get("final_weight", pd.Series(dtype=float))), errors="coerce").fillna(0.0)
    hhi = float(np.square(weights).sum()) if not weights.empty else None
    final_trade_actions = bundle.frames.get("portfolio_trade_list", pd.DataFrame())
    action_col = resolve_column(final_trade_actions, "recommendation")
    top_actions = tuple(final_trade_actions[action_col].astype(str).head(5)) if action_col else ()
    forecast_12m = bundle.frames.get("ml_forecasts_12m", pd.DataFrame())
    if forecast_12m.empty:
        forecast_12m = final_portfolio
    weight_col = "target_weight" if "target_weight" in final_portfolio else "final_weight"
    summary: dict[str, object] = {
        "model_run_id": bundle.model_run_id,
        "as_of_date": str(bundle.as_of_date.date()) if hasattr(bundle.as_of_date, "date") else str(bundle.as_of_date),
        "decision_readiness_status": _readiness(
            bundle,
            resolved,
            hard_breaches,
            pdf_available,
            report_quality,
        ),
        "current_nav_usd": float(pd.to_numeric(current.get("market_value_usd", pd.Series(dtype=float)), errors="coerce").sum()) if not current.empty else None,
        "selected_portfolio_source": resolved.source_name if resolved is not None else "unavailable",
        "recommended_positions": int((weights > 0).sum()) if not weights.empty else 0,
        "top_recommendation": final_portfolio.iloc[0].get("ticker", "Unavailable") if not final_portfolio.empty else "Unavailable",
        "dominant_regime": regime.iloc[-1].get("dominant_regime", "Unavailable") if not regime.empty else "Unavailable",
        "wolf_chaos_index": regime.iloc[-1].get("wolf_chaos_index", "Unavailable") if not regime.empty else "Unavailable",
        "worst_stress_scenario": stress.sort_values("portfolio_loss_pct").iloc[0].get("scenario_name", "Unavailable") if not stress.empty and "portfolio_loss_pct" in stress else "Unavailable",
        "worst_stress_loss": _first_numeric(stress.sort_values("portfolio_loss_pct") if "portfolio_loss_pct" in stress else stress, ("portfolio_loss_pct", "loss_pct")),
        "drl_status": drl.iloc[-1].get("selected_weights_source", "Unavailable") if not drl.empty else "Unavailable",
        "number_of_hard_constraint_breaches": hard_breaches,
        "maximum_single_name_weight": float(weights.max()) if not weights.empty else None,
        "hhi": hhi,
        "effective_number_of_holdings": float(1.0 / hhi) if hhi and hhi > 0 else None,
        "top_actions": top_actions,
    }
    summary["expected_total_return_12m"] = weighted_average(final_portfolio, "expected_total_return_12m", weight_col)
    summary["expected_dividend_yield"] = weighted_average(final_portfolio, "dividend_yield", weight_col)
    summary["p5_return_12m"] = weighted_average(forecast_12m, "p5_return_12m", weight_col) or _first_numeric(forecast_12m, ("p5_return_12m", "p5_return"))
    summary["p50_return_12m"] = weighted_average(forecast_12m, "p50_return_12m", weight_col) or _first_numeric(forecast_12m, ("p50_return_12m", "p50_return"))
    summary["p95_return_12m"] = weighted_average(forecast_12m, "p95_return_12m", weight_col) or _first_numeric(forecast_12m, ("p95_return_12m", "p95_return"))
    for column in ["portfolio_var_5", "portfolio_cvar_5", "portfolio_expected_shortfall_5", "portfolio_expected_total_return"]:
        summary[column] = risk.iloc[-1].get(column, "Unavailable") if not risk.empty else "Unavailable"
    return summary
