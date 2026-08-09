from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.reporting.column_resolver import canonicalise_dataframe, first_existing, resolve_column
from src.reporting.models import ICDataBundle


@dataclass(frozen=True)
class ResolvedPortfolio:
    portfolio: pd.DataFrame
    source_name: str
    fallback_used: bool
    warnings: tuple[str, ...]


def _valid_weight_frame(data: pd.DataFrame) -> bool:
    if data.empty:
        return False
    weight_column = resolve_column(data, "target_weight")
    if weight_column is None:
        return False
    weights = pd.to_numeric(data[weight_column], errors="coerce")
    return bool(weights.notna().all() and (weights >= -1e-10).all() and np.isclose(weights.sum(), 1.0, atol=1e-5))


def _normalise_portfolio(data: pd.DataFrame, source_name: str) -> pd.DataFrame:
    frame = canonicalise_dataframe(data)
    if frame.empty:
        return frame
    target_col = resolve_column(frame, "target_weight", required=True)
    ticker_col = resolve_column(frame, "ticker")
    security_col = resolve_column(frame, "security_id")
    company_col = resolve_column(frame, "company_name")
    output = frame.copy()
    output["target_weight"] = pd.to_numeric(output[target_col], errors="coerce").fillna(0.0).clip(lower=0.0)
    output["final_weight"] = output["target_weight"]
    output["source"] = source_name
    if ticker_col and "ticker" not in output:
        output["ticker"] = output[ticker_col].astype(str)
    if security_col and "security_id" not in output:
        output["security_id"] = output[security_col].astype(str)
    if "security_id" not in output:
        output["security_id"] = output.get("ticker", pd.Series(range(len(output)), index=output.index)).astype(str)
    if company_col and "company_name" not in output:
        output["company_name"] = output[company_col].astype(str)
    if "ticker" not in output:
        output["ticker"] = output["security_id"].astype(str)
    if "company_name" not in output:
        output["company_name"] = output["ticker"].astype(str)
    return output.sort_values("target_weight", ascending=False).reset_index(drop=True)


def resolve_final_portfolio(
    explicit_final: pd.DataFrame,
    drl_weights: pd.DataFrame | None = None,
    drl_status: str | None = None,
    selected_optimiser: pd.DataFrame | None = None,
    cvar_portfolio: pd.DataFrame | None = None,
    regime_portfolio: pd.DataFrame | None = None,
    score_portfolio: pd.DataFrame | None = None,
    equal_weight_portfolio: pd.DataFrame | None = None,
) -> ResolvedPortfolio:
    candidates: list[tuple[str, pd.DataFrame, bool]] = [("explicit_final_portfolio", explicit_final, False)]
    if drl_status in {"accepted", "blended", "accept_challenger", "accepted_blended", "drl_challenger"}:
        candidates.append(("accepted_drl_blend", drl_weights if drl_weights is not None else pd.DataFrame(), False))
    candidates.extend(
        [
            ("selected_constrained_optimiser", selected_optimiser if selected_optimiser is not None else pd.DataFrame(), False),
            ("cvar_constrained", cvar_portfolio if cvar_portfolio is not None else pd.DataFrame(), True),
            ("regime_aware", regime_portfolio if regime_portfolio is not None else pd.DataFrame(), True),
            ("score_weighted", score_portfolio if score_portfolio is not None else pd.DataFrame(), True),
            ("equal_weight_fallback", equal_weight_portfolio if equal_weight_portfolio is not None else pd.DataFrame(), True),
        ]
    )
    warnings = []
    if drl_status and drl_status not in {"accepted", "blended", "accept_challenger", "accepted_blended", "drl_challenger"}:
        warnings.append("Raw DRL weights ignored because DRL was not accepted or blended.")
    for source_name, portfolio, fallback in candidates:
        if _valid_weight_frame(portfolio):
            return ResolvedPortfolio(_normalise_portfolio(portfolio, source_name), source_name, fallback, tuple(warnings))
    raise RuntimeError("No valid final portfolio could be resolved.")


def _drl_status(bundle: ICDataBundle) -> str | None:
    status = bundle.frames.get("drl_acceptance", pd.DataFrame())
    if status.empty:
        return None
    for column in ("accepted", "deployment_mode", "selected_weights_source", "acceptance_status"):
        if column in status:
            value = status.iloc[-1][column]
            if column == "accepted":
                return "accepted" if bool(value) else "rejected"
            return str(value).lower()
    return None


def _selected_optimiser(bundle: ICDataBundle) -> pd.DataFrame:
    summary = bundle.frames.get("portfolio_optimisation_summary", pd.DataFrame())
    if summary.empty:
        return pd.DataFrame()
    if {"selected_recommended_portfolio", "portfolio_method"}.issubset(summary.columns):
        selected = summary[
            summary["selected_recommended_portfolio"].astype(str).str.strip().str.lower().isin({"true", "1", "yes"})
        ]
        if not selected.empty:
            key = str(selected.iloc[-1]["portfolio_method"]).lower().replace("-", "_").replace(" ", "_")
            return bundle.frames.get(f"optimised_portfolio_{key}", pd.DataFrame())
    for column in ("selected_portfolio", "selected_strategy", "portfolio_name", "recommended_portfolio"):
        if column in summary:
            key = str(summary.iloc[-1][column]).lower().replace("-", "_").replace(" ", "_")
            return bundle.frames.get(f"optimised_portfolio_{key}", pd.DataFrame())
    return pd.DataFrame()


def _equal_weight_fallback(bundle: ICDataBundle) -> pd.DataFrame:
    base = bundle.frames.get("final_recommendations", pd.DataFrame())
    if base.empty:
        base = bundle.frames.get("current_portfolio", pd.DataFrame())
    if base.empty:
        return pd.DataFrame()
    frame = canonicalise_dataframe(base)
    eligible_col = first_existing(["eligible", "is_eligible", "passes_hard_filters", "exclude"], frame)
    if eligible_col:
        values = frame[eligible_col]
        if eligible_col == "exclude":
            frame = frame[~values.astype(bool)]
        else:
            frame = frame[values.astype(bool)]
    if frame.empty:
        return pd.DataFrame()
    frame = frame.copy()
    frame["target_weight"] = 1.0 / len(frame)
    return frame


def resolve_final_portfolio_from_bundle(bundle: ICDataBundle) -> ResolvedPortfolio:
    return resolve_final_portfolio(
        explicit_final=bundle.frames.get("final_portfolio_weights", pd.DataFrame()),
        drl_weights=bundle.frames.get("drl_target_weights", pd.DataFrame()),
        drl_status=_drl_status(bundle),
        selected_optimiser=_selected_optimiser(bundle),
        cvar_portfolio=bundle.frames.get("optimised_portfolio_cvar_constrained", pd.DataFrame()),
        regime_portfolio=bundle.frames.get("optimised_portfolio_regime_aware", pd.DataFrame()),
        score_portfolio=bundle.frames.get("optimised_portfolio_score_weighted", pd.DataFrame()),
        equal_weight_portfolio=_equal_weight_fallback(bundle),
    )


def classify_trade_action(current_weight: float, target_weight: float, excluded: bool, threshold: float = 0.0025) -> str:
    if excluded and target_weight <= 1e-10:
        return "Avoid" if current_weight <= 1e-10 else "Exit"
    difference = target_weight - current_weight
    if difference > threshold:
        return "Buy" if current_weight <= threshold else "Increase"
    if difference < -threshold:
        return "Exit" if target_weight <= threshold else "Reduce"
    return "Hold"


def build_final_trade_recommendations(bundle: ICDataBundle, resolved: ResolvedPortfolio, nav_usd: float | None = None) -> pd.DataFrame:
    current = canonicalise_dataframe(bundle.frames.get("current_portfolio", pd.DataFrame()))
    target = canonicalise_dataframe(resolved.portfolio)
    if current.empty:
        current = pd.DataFrame({"security_id": pd.Series(dtype=str), "current_weight": pd.Series(dtype=float)})
    if target.empty:
        return pd.DataFrame()
    if "security_id" not in current and "ticker" in current:
        current = current.copy()
        current["security_id"] = current["ticker"].astype(str)
    if "security_id" not in target and "ticker" in target:
        target = target.copy()
        target["security_id"] = target["ticker"].astype(str)
    current_weight_col = resolve_column(current, "current_weight")
    if current_weight_col is None and "market_value_usd" in current:
        total_nav = pd.to_numeric(current["market_value_usd"], errors="coerce").sum()
        current = current.copy()
        current["current_weight"] = pd.to_numeric(current["market_value_usd"], errors="coerce").fillna(0.0) / total_nav if total_nav > 0 else 0.0
        current_weight_col = "current_weight"
    if nav_usd is None:
        nav_usd = float(pd.to_numeric(current.get("market_value_usd", pd.Series(dtype=float)), errors="coerce").sum() or 0.0)
    merged = target.merge(current, on="security_id", how="outer", suffixes=("_target", "_current"))
    merged["target_weight"] = pd.to_numeric(merged.get("target_weight", merged.get("final_weight", 0.0)), errors="coerce").fillna(0.0)
    merged["current_weight"] = pd.to_numeric(merged.get(current_weight_col or "current_weight", merged.get("current_weight_current", 0.0)), errors="coerce").fillna(0.0)
    merged["weight_change"] = merged["target_weight"] - merged["current_weight"]
    zero_series = pd.Series(0.0, index=merged.index)
    merged["current_market_value_usd"] = pd.to_numeric(
        merged.get("market_value_usd", merged.get("market_value_usd_current", zero_series)),
        errors="coerce",
    ).fillna(0.0)
    merged["target_market_value_usd"] = merged["target_weight"] * float(nav_usd or 0.0)
    merged["trade_notional_usd"] = merged["weight_change"] * float(nav_usd or 0.0)
    excluded = merged.get("exclude", merged.get("excluded", pd.Series(False, index=merged.index))).fillna(False).astype(bool)
    merged["trade_action"] = [
        classify_trade_action(float(cw), float(tw), bool(exc))
        for cw, tw, exc in zip(merged["current_weight"], merged["target_weight"], excluded)
    ]
    for column in (
        "ticker",
        "company_name",
        "country",
        "region",
        "sector",
        "currency",
        "expected_total_return_12m",
        "expected_dividend_yield",
        "p5_return_12m",
        "p50_return_12m",
        "p95_return_12m",
        "var_5",
        "cvar_5",
        "expected_shortfall_5",
        "dividend_cut_probability",
        "drawdown_probability",
        "regime_suitability_score",
        "final_recommendation_score",
        "primary_positive_driver",
        "primary_risk",
        "constraint_flags",
        "drl_effect",
        "rationale",
    ):
        target_col = f"{column}_target"
        current_col = f"{column}_current"
        if column not in merged:
            merged[column] = merged.get(target_col, merged.get(current_col, ""))
    merged["source_trace"] = resolved.source_name
    required = [
        "security_id",
        "ticker",
        "company_name",
        "country",
        "region",
        "sector",
        "currency",
        "current_weight",
        "target_weight",
        "weight_change",
        "current_market_value_usd",
        "target_market_value_usd",
        "trade_notional_usd",
        "trade_action",
        "expected_total_return_12m",
        "expected_dividend_yield",
        "p5_return_12m",
        "p50_return_12m",
        "p95_return_12m",
        "var_5",
        "cvar_5",
        "expected_shortfall_5",
        "dividend_cut_probability",
        "drawdown_probability",
        "regime_suitability_score",
        "final_recommendation_score",
        "primary_positive_driver",
        "primary_risk",
        "constraint_flags",
        "drl_effect",
        "rationale",
        "source_trace",
    ]
    for column in required:
        if column not in merged:
            merged[column] = ""
    return merged[required].sort_values("trade_notional_usd", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)
