from __future__ import annotations

import pandas as pd


def classify_chaos_regime(chaos_index: pd.DataFrame, low_max: float = 35, intermediate_max: float = 70) -> pd.DataFrame:
    """Classify Wolf Chaos Index into low/intermediate/high chaos probabilities."""
    row = chaos_index.iloc[0].to_dict()
    index = float(row["wolf_chaos_index"])
    if index < low_max:
        probs = {"low_chaos_probability": 0.75, "intermediate_chaos_probability": 0.20, "high_chaos_probability": 0.05}
        dominant = "low_chaos"
    elif index < intermediate_max:
        probs = {"low_chaos_probability": 0.15, "intermediate_chaos_probability": 0.70, "high_chaos_probability": 0.15}
        dominant = "intermediate_chaos"
    else:
        probs = {"low_chaos_probability": 0.05, "intermediate_chaos_probability": 0.20, "high_chaos_probability": 0.75}
        dominant = "high_chaos"
    confidence = max(probs.values())
    return pd.DataFrame([{**row, **probs, "dominant_chaos_regime": dominant, "chaos_regime_confidence": confidence, "chaos_regime_change_flag": index >= intermediate_max}])
