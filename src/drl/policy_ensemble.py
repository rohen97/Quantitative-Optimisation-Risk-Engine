from __future__ import annotations

import numpy as np
import pandas as pd

from src.drl.ppo_agent import MockPPOAgent
from src.drl.regime_gating import RiskThrottle
from src.drl.specialist_agents import (
    credit_stress_action,
    crisis_high_chaos_action,
    inflation_action,
    regional_stress_action,
    stable_low_chaos_action,
)


def apply_risk_throttle(action: np.ndarray, throttle: RiskThrottle | None) -> np.ndarray:
    """Apply calibrated distribution-shift throttle to a residual action."""
    if throttle is None:
        return np.asarray(action, dtype=float)
    adjusted = np.asarray(action, dtype=float) * float(throttle.action_scale)
    if throttle.additions_blocked:
        adjusted = np.minimum(adjusted, 0.0)
    if throttle.fallback_to_baseline:
        adjusted = np.zeros_like(adjusted)
    return adjusted


def build_regime_gated_action(
    asset_data: pd.DataFrame,
    gate_weights: pd.DataFrame,
    seed: int,
    max_adjustment: float,
    throttle: RiskThrottle | None = None,
) -> np.ndarray:
    """Blend core PPO and specialist agent actions using regime probabilities."""
    core = MockPPOAgent(seed=seed, max_adjustment=max_adjustment).predict(asset_data)
    stable = stable_low_chaos_action(asset_data, scale=max_adjustment)
    crisis = crisis_high_chaos_action(asset_data, scale=max_adjustment)
    inflation = inflation_action(asset_data, scale=max_adjustment * 0.5)
    regional = regional_stress_action(asset_data, scale=max_adjustment * 0.5)
    credit = credit_stress_action(asset_data, scale=max_adjustment * 0.5)
    weights = gate_weights.set_index("agent")["agent_weight"].to_dict()
    if throttle is not None and throttle.defensive_only:
        weights = {
            "stable_low_chaos_agent": 0.10,
            "crisis_high_chaos_agent": 0.75,
            "inflation_agent": 0.05,
            "regional_stress_agent": 0.05,
            "credit_stress_agent": 0.05,
        }
    core_weight = 0.20 if not (throttle is not None and throttle.defensive_only) else 0.0
    specialist_weight = max(0.0, 1.0 - core_weight)
    action = (
        core_weight * core
        + specialist_weight
        * (
            weights.get("stable_low_chaos_agent", 0.50) * stable
            + weights.get("crisis_high_chaos_agent", 0.50) * crisis
            + weights.get("inflation_agent", 0.0) * inflation
            + weights.get("regional_stress_agent", 0.0) * regional
            + weights.get("credit_stress_agent", 0.0) * credit
        )
    )
    return apply_risk_throttle(np.asarray(action, dtype=float).clip(-max_adjustment, max_adjustment), throttle)
