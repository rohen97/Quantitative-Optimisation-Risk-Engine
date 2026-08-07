from __future__ import annotations

import pandas as pd


def fuse_regime_signals(
    factor_probabilities: pd.DataFrame,
    chaos_probabilities: pd.DataFrame,
    informational_drivers: pd.DataFrame,
) -> pd.DataFrame:
    """Fuse factor, chaos and informational drivers into a dominant market regime."""
    factor = factor_probabilities.iloc[0]
    chaos = chaos_probabilities.iloc[0]
    drivers = informational_drivers.iloc[0]
    deterioration = float(drivers["regime_deterioration_probability"])
    dominant = "steady_state_low_chaos"
    if factor["crisis_probability"] > 0.35 and chaos["high_chaos_probability"] > 0.35:
        dominant = "crisis_high_chaos"
    elif chaos["high_chaos_probability"] > 0.50:
        dominant = "risk_on_fragile"
    elif drivers.get("credit_stress_news", 0) > 75:
        dominant = "credit_stress"
    elif drivers.get("europe_recession_uncertainty", 0) > 60:
        dominant = "europe_recession"
    elif drivers.get("china_policy_uncertainty", 0) > 70:
        dominant = "china_policy_stress"
    elif drivers.get("uk_rate_uncertainty", 0) > 60:
        dominant = "uk_rate_pressure"
    elif factor["inflation_probability"] > 0.35:
        dominant = "inflation_pressure"
    elif factor["walking_on_ice_probability"] > 0.30 and chaos["intermediate_chaos_probability"] + chaos["high_chaos_probability"] > 0.50:
        dominant = "risk_on_fragile"
    probabilities = [
        factor["crisis_probability"],
        factor["steady_state_probability"],
        factor["inflation_probability"],
        factor["walking_on_ice_probability"],
    ]
    confidence = max(probabilities + [chaos["low_chaos_probability"], chaos["intermediate_chaos_probability"], chaos["high_chaos_probability"]])
    if confidence < 0.35:
        dominant = "mixed_transition"
    weighted_risk = 35 * factor["crisis_probability"] + 35 * chaos["high_chaos_probability"] + 30 * deterioration
    risk_score = min(100, max(weighted_risk, 100 * chaos["high_chaos_probability"]))
    as_of_date = factor.get("as_of_date", chaos.get("as_of_date", drivers.get("as_of_date", pd.Timestamp.today().normalize())))
    return pd.DataFrame(
        [
            {
                "as_of_date": as_of_date,
                "dominant_regime": dominant,
                "regime_confidence": confidence,
                "regime_risk_score": risk_score,
                "regime_deterioration_probability": deterioration,
                "regime_stability_score": max(0, 100 - risk_score),
                "crisis_probability": factor["crisis_probability"],
                "steady_state_probability": factor["steady_state_probability"],
                "inflation_probability": factor["inflation_probability"],
                "walking_on_ice_probability": factor["walking_on_ice_probability"],
                "low_chaos_probability": chaos["low_chaos_probability"],
                "intermediate_chaos_probability": chaos["intermediate_chaos_probability"],
                "high_chaos_probability": chaos["high_chaos_probability"],
                "wolf_chaos_index": chaos["wolf_chaos_index"],
                "top_regime_driver_1": drivers.get("top_regime_driver_1", drivers.get("top_driver_1", "")),
                "top_regime_driver_2": drivers.get("top_regime_driver_2", drivers.get("top_driver_2", "")),
                "top_regime_driver_3": drivers.get("top_regime_driver_3", drivers.get("top_driver_3", "")),
            }
        ]
    )
