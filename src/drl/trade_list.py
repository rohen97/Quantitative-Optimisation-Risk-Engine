from __future__ import annotations

import numpy as np
import pandas as pd

from src.drl.benchmark import DRLAcceptanceDecision
from src.drl.explainability import _driver_lists


DRL_TRADE_LIST_COLUMNS = [
    "security_id",
    "ticker",
    "company_name",
    "current_weight",
    "baseline_weight",
    "raw_drl_weight",
    "projected_drl_weight",
    "accepted_blended_weight",
    "weight_change_vs_current",
    "weight_change_vs_baseline",
    "trade_action",
    "trade_size_usd",
    "transaction_cost_estimate",
    "slippage_estimate",
    "liquidity_impact",
    "primary_positive_driver",
    "primary_negative_driver",
    "regime_effect",
    "risk_effect",
    "constraint_adjustment",
    "acceptance_status",
    "commentary",
]


def _numeric(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column in frame:
        values = frame[column]
    else:
        values = pd.Series(default, index=frame.index)
    return pd.to_numeric(values, errors="coerce").fillna(default)


def _friction_config(config: dict | None) -> dict[str, float]:
    raw = (config or {}).get("market_friction", config or {})
    return {
        "commission_bps": float(raw.get("commission_bps", raw.get("transaction_cost_bps", 12.0))),
        "half_spread_bps": float(raw.get("half_spread_bps", raw.get("slippage_bps", 5.0))),
        "impact_coefficient": float(raw.get("impact_coefficient", 10.0)),
        "missing_adv_usd": float(raw.get("missing_adv_usd", 5_000_000.0)),
        "minimum_adv_usd": float(raw.get("minimum_adv_usd", 1_000_000.0)),
        "max_participation_rate": float(raw.get("max_participation_rate", 0.25)),
    }


def _trade_action(row: pd.Series, accepted: bool, threshold: float) -> str:
    current = float(row["current_weight"])
    accepted_weight = float(row["accepted_blended_weight"])
    eligible = bool(row.get("eligible_for_drl", True))
    if not accepted:
        return "Baseline Fallback"
    if not eligible:
        return "Exit" if current > threshold and accepted_weight <= threshold else "Avoid"
    if accepted_weight <= threshold and current > threshold:
        return "Exit"
    if accepted_weight > threshold and current <= threshold:
        return "Buy"
    if accepted_weight > current + threshold:
        return "Increase"
    if accepted_weight < current - threshold:
        return "Reduce"
    return "Hold"


def _regime_effect(row: pd.Series) -> str:
    score = float(row.get("regime_suitability_score", 50.0))
    if score >= 65:
        return "regime suitability contributed positively to the model allocation"
    if score <= 40:
        return "regime suitability was associated with lower model appetite"
    return "regime effect was neutral to moderate"


def _risk_effect(row: pd.Series) -> str:
    cvar = float(row.get("cvar_5_12m", -0.20))
    drawdown = float(row.get("large_drawdown_probability_12m", 0.20))
    dividend_cut = float(row.get("dividend_cut_probability", 0.10))
    if cvar < -0.25 or drawdown > 0.35 or dividend_cut > 0.35:
        return "risk metrics were associated with lower allocation confidence"
    return "risk metrics were within the model's conservative review range"


def _commentary(row: pd.Series) -> str:
    action = str(row["trade_action"])
    ticker = str(row["ticker"])
    if action == "Baseline Fallback":
        return f"{ticker}: DRL allocation rejected by acceptance rules; baseline optimiser weight selected."
    if action in {"Buy", "Increase"}:
        return f"{ticker}: model attributions supported a higher accepted weight after constraints."
    if action in {"Reduce", "Exit"}:
        return f"{ticker}: risk, eligibility or projection review contributed to a lower accepted weight."
    if action == "Avoid":
        return f"{ticker}: security remains outside the executable DRL allocation."
    return f"{ticker}: accepted blended weight is close to the current portfolio weight."


def build_drl_trade_list(
    asset_data: pd.DataFrame,
    projection_report: pd.DataFrame,
    accepted_weights: np.ndarray,
    acceptance: DRLAcceptanceDecision,
    nav_usd: float,
    config: dict | None = None,
    threshold: float = 0.0025,
) -> pd.DataFrame:
    """Build the executable DRL trade list with raw, projected and accepted weights."""
    data = asset_data.reset_index(drop=True).copy()
    report = projection_report[projection_report["ticker"].astype(str).str.upper().ne("CASH")].reset_index(drop=True).copy()
    if len(report) != len(data):
        raise ValueError("projection_report must contain one non-cash row per asset.")
    accepted = np.asarray(accepted_weights, dtype=float)
    if accepted.shape[0] != len(data):
        raise ValueError("accepted_weights length must match asset_data.")
    nav = max(float(nav_usd), 1.0)
    friction = _friction_config(config)

    out = pd.DataFrame(index=data.index)
    for column in ["security_id", "ticker", "company_name"]:
        out[column] = data[column] if column in data else data.get("ticker", pd.Series(data.index, index=data.index))
    out["current_weight"] = _numeric(data, "current_weight")
    out["baseline_weight"] = pd.to_numeric(report["baseline_weight"], errors="coerce").fillna(0.0)
    out["raw_drl_weight"] = pd.to_numeric(report["candidate_weight"], errors="coerce").fillna(out["baseline_weight"])
    out["projected_drl_weight"] = pd.to_numeric(report["projected_weight"], errors="coerce").fillna(0.0)
    out["accepted_blended_weight"] = accepted
    out["eligible_for_drl"] = report.get("eligible_for_drl", pd.Series(True, index=report.index)).fillna(False).astype(bool).to_numpy()
    out["weight_change_vs_current"] = out["accepted_blended_weight"] - out["current_weight"]
    out["weight_change_vs_baseline"] = out["accepted_blended_weight"] - out["baseline_weight"]
    out["trade_action"] = out.apply(_trade_action, axis=1, accepted=acceptance.accepted, threshold=threshold)
    out["trade_size_usd"] = out["weight_change_vs_current"] * nav

    traded_notional = out["weight_change_vs_current"].abs() * nav
    out["transaction_cost_estimate"] = traded_notional * friction["commission_bps"] / 10_000
    out["slippage_estimate"] = traded_notional * friction["half_spread_bps"] / 10_000
    adv = _numeric(data, "average_daily_value_usd", friction["missing_adv_usd"]).clip(lower=friction["minimum_adv_usd"])
    participation = (traded_notional / adv).clip(lower=0.0, upper=friction["max_participation_rate"])
    out["liquidity_impact"] = traded_notional * (friction["impact_coefficient"] * np.sqrt(participation)) / 10_000

    positives = []
    negatives = []
    for _, row in data.iterrows():
        pos, neg = _driver_lists(row)
        positives.append(pos[0])
        negatives.append(neg[0])
    out["primary_positive_driver"] = positives
    out["primary_negative_driver"] = negatives
    out["regime_effect"] = data.apply(_regime_effect, axis=1)
    out["risk_effect"] = data.apply(_risk_effect, axis=1)
    out["constraint_adjustment"] = (out["raw_drl_weight"] - out["projected_drl_weight"]).abs()
    out["acceptance_status"] = "Accepted" if acceptance.accepted else "Rejected - Baseline Fallback"
    out["commentary"] = out.apply(_commentary, axis=1)

    return (
        out[DRL_TRADE_LIST_COLUMNS]
        .sort_values("trade_size_usd", key=lambda values: values.abs(), ascending=False)
        .reset_index(drop=True)
    )
