from __future__ import annotations

import pandas as pd


def classify_regime(inputs: dict[str, float]) -> str:
    if inputs.get("china_policy_pressure", 0) > 0.7:
        return "China policy stress"
    if inputs.get("inflation_surprise", 0) > 0.6:
        return "Inflation shock"
    if inputs.get("growth_trend", 0) < -0.4:
        return "Defensive / low growth"
    return "Risk-on recovery"


def build_regime_scores(universe: pd.DataFrame, regime_label: str = "Defensive / low growth") -> pd.DataFrame:
    defensive = {"Healthcare", "Consumer Staples", "Utilities"}
    data = universe[["ticker", "sector", "region"]].copy()
    data["regime_label"] = regime_label
    data["regime_probability"] = 0.68
    data["regime_suitability_score"] = data["sector"].isin(defensive).map({True: 82, False: 58}).astype(float)
    return data[["ticker", "regime_label", "regime_probability", "regime_suitability_score"]]
