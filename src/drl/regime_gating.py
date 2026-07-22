from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RiskThrottle:
    action_scale: float
    minimum_cash_weight: float
    defensive_only: bool
    additions_blocked: bool
    fallback_to_baseline: bool
    reason: str


def calculate_risk_throttle(
    wolf_chaos_index: float,
    high_chaos_probability: float,
    crisis_probability: float,
    regime_deterioration_probability: float,
    credit_stress_probability: float,
) -> RiskThrottle:
    """Convert calibrated regime/stress probabilities into DRL action limits."""
    wolf = float(np.nan_to_num(wolf_chaos_index, nan=0.0))
    high_chaos = float(np.nan_to_num(high_chaos_probability, nan=0.0))
    crisis = float(np.nan_to_num(crisis_probability, nan=0.0))
    deterioration = float(np.nan_to_num(regime_deterioration_probability, nan=0.0))
    credit = float(np.nan_to_num(credit_stress_probability, nan=0.0))
    if wolf >= 85 or high_chaos >= 0.65 or crisis >= 0.55 or deterioration >= 0.70 or credit >= 0.60:
        return RiskThrottle(
            action_scale=0.0,
            minimum_cash_weight=0.20,
            defensive_only=True,
            additions_blocked=True,
            fallback_to_baseline=True,
            reason="extreme_distribution_shift_or_crisis_risk",
        )
    if wolf >= 70 or high_chaos >= 0.45 or crisis >= 0.35 or deterioration >= 0.50 or credit >= 0.40:
        return RiskThrottle(
            action_scale=0.25,
            minimum_cash_weight=0.10,
            defensive_only=True,
            additions_blocked=True,
            fallback_to_baseline=False,
            reason="severe_regime_risk_defensive_only",
        )
    if wolf >= 55 or high_chaos >= 0.30 or crisis >= 0.25 or deterioration >= 0.35 or credit >= 0.25:
        return RiskThrottle(
            action_scale=0.50,
            minimum_cash_weight=0.05,
            defensive_only=False,
            additions_blocked=False,
            fallback_to_baseline=False,
            reason="elevated_uncertainty_scaled_actions",
        )
    return RiskThrottle(
        action_scale=1.0,
        minimum_cash_weight=0.02,
        defensive_only=False,
        additions_blocked=False,
        fallback_to_baseline=False,
        reason="normal_risk_budget",
    )


def calculate_risk_throttle_from_dashboard(regime_dashboard: pd.DataFrame | None) -> RiskThrottle:
    """Build a risk throttle from the regime dashboard with safe neutral fallbacks."""
    row = {} if regime_dashboard is None or regime_dashboard.empty else regime_dashboard.iloc[0].to_dict()
    return calculate_risk_throttle(
        wolf_chaos_index=float(row.get("wolf_chaos_index", row.get("Wolf Chaos Index", 0.0))),
        high_chaos_probability=float(row.get("high_chaos_probability", 0.0)),
        crisis_probability=float(row.get("crisis_probability", 0.0)),
        regime_deterioration_probability=float(row.get("regime_deterioration_probability", 0.0)),
        credit_stress_probability=float(row.get("credit_stress_probability", row.get("credit_stress_similarity", 0.0))),
    )


def risk_throttle_frame(throttle: RiskThrottle) -> pd.DataFrame:
    """Return the throttle as a one-row report frame."""
    return pd.DataFrame([throttle.__dict__])


def blend_specialist_weights(
    stable_weights: np.ndarray,
    crisis_weights: np.ndarray,
    stable_probability: float,
    crisis_probability: float,
) -> np.ndarray:
    """Blend stable and crisis specialist portfolios probabilistically."""
    probs = np.array([max(float(stable_probability), 0.0), max(float(crisis_probability), 0.0)], dtype=float)
    if probs.sum() <= 0:
        probs[:] = 0.5
    probs /= probs.sum()
    weights = probs[0] * np.asarray(stable_weights, dtype=float) + probs[1] * np.asarray(crisis_weights, dtype=float)
    weights = np.maximum(weights, 0.0)
    total = float(weights.sum())
    if total <= 0:
        raise ValueError("Specialist blend produced zero total weight.")
    return weights / total


def map_regime_specialist_probabilities(regime_dashboard: pd.DataFrame | None) -> dict[str, float]:
    """Map regime probabilities to specialist-agent blend probabilities."""
    row = {} if regime_dashboard is None or regime_dashboard.empty else regime_dashboard.iloc[0].to_dict()
    stable = float(row.get("steady_state_probability", 0.50)) + 0.5 * float(row.get("low_chaos_probability", 0.50))
    crisis = (
        float(row.get("crisis_probability", 0.10))
        + float(row.get("high_chaos_probability", 0.10))
        + 0.5 * float(row.get("regime_deterioration_probability", 0.10))
    )
    inflation = float(row.get("inflation_probability", 0.0))
    regional = float(row.get("walking_on_ice_probability", 0.0))
    credit = float(row.get("credit_stress_probability", row.get("credit_stress_similarity", 0.0)))
    probs = {
        "stable_low_chaos_agent": max(stable, 0.0),
        "crisis_high_chaos_agent": max(crisis, 0.0),
        "inflation_agent": max(inflation, 0.0),
        "regional_stress_agent": max(regional, 0.0),
        "credit_stress_agent": max(credit, 0.0),
    }
    total = sum(probs.values())
    if total <= 0:
        probs["stable_low_chaos_agent"] = 0.5
        probs["crisis_high_chaos_agent"] = 0.5
        total = 1.0
    return {key: value / total for key, value in probs.items()}


def calculate_regime_agent_weights(regime_dashboard: pd.DataFrame | None) -> pd.DataFrame:
    """Convert regime probabilities into specialist-agent blend weights."""
    probs = map_regime_specialist_probabilities(regime_dashboard)
    status = {
        "stable_low_chaos_agent": "mvp_active",
        "crisis_high_chaos_agent": "mvp_active",
        "inflation_agent": "future_ready",
        "regional_stress_agent": "future_ready",
        "credit_stress_agent": "future_ready",
    }
    return pd.DataFrame(
        [{"agent": agent, "agent_weight": weight, "agent_status": status[agent]} for agent, weight in probs.items()]
    )
