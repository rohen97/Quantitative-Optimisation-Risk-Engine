from __future__ import annotations

import numpy as np
import pandas as pd


def estimate_drawdown_probability(features: pd.DataFrame, regime_dashboard: pd.DataFrame | None = None) -> pd.DataFrame:
    """Estimate large-drawdown probabilities across forecast horizons."""
    data = features.copy()
    chaos = 0.0
    high_chaos = 0.0
    if regime_dashboard is not None and not regime_dashboard.empty:
        chaos = float(regime_dashboard.iloc[0].get("wolf_chaos_index", 0))
        high_chaos = float(regime_dashboard.iloc[0].get("high_chaos_probability", 0))
    vol = data.get("volatility_1y", pd.Series(0.20, index=data.index)).fillna(0.20)
    beta = data.get("beta_local_market", pd.Series(1.0, index=data.index)).fillna(1.0)
    global_beta = data.get("beta_global_market", beta).fillna(beta)
    max_dd = data.get("max_drawdown_1y", pd.Series(-0.12, index=data.index)).fillna(-0.12).abs()
    downside = data.get("downside_volatility", pd.Series(vol, index=data.index)).fillna(vol)
    cvar = data.get("cvar_5", pd.Series(-0.08, index=data.index)).fillna(-0.08).abs()
    liquidity = data.get("liquidity_stress_score", pd.Series(0, index=data.index)).fillna(0)
    risk_frame = data.get("risk_reframing_score", pd.Series(50, index=data.index)).fillna(50)
    distress = data.get("distress_similarity_score", pd.Series(50, index=data.index)).fillna(50)
    credit = data.get("credit_stress_similarity_score", data.get("credit_stress_score", pd.Series(0, index=data.index))).fillna(0)
    regime_risk = data.get("regime_risk_score", pd.Series(50, index=data.index)).fillna(50)
    deterioration = data.get("regime_deterioration_probability", pd.Series(0, index=data.index)).fillna(0)
    base = (
        0.03
        + 0.16 * (vol / 0.45).clip(0, 1)
        + 0.06 * ((beta + global_beta) / 2 - 1).clip(0, 1.5) / 1.5
        + 0.07 * (max_dd / 0.45).clip(0, 1)
        + 0.05 * (downside / 0.35).clip(0, 1)
        + 0.04 * (cvar / 0.25).clip(0, 1)
        + 0.04 * (liquidity / 100).clip(0, 1)
        + 0.04 * (risk_frame / 100).clip(0, 1)
        + 0.04 * (distress / 100).clip(0, 1)
        + 0.04 * (credit / 100).clip(0, 1)
        + 0.04 * (regime_risk / 100).clip(0, 1)
        + 0.04 * deterioration.clip(0, 1)
        + 0.04 * high_chaos
        + 0.03 * chaos / 100
    ).clip(0, 0.95)
    output = data[[col for col in ["security_id", "ticker", "company_name"] if col in data]].copy()
    for months, scale in {3: 0.55, 6: 0.75, 9: 0.90, 12: 1.0}.items():
        output[f"large_drawdown_probability_{months}m"] = (base * scale).clip(0, 0.95)
        output[f"expected_max_drawdown_{months}m"] = -(0.04 + vol * np.sqrt(months / 12) * 0.95 + output[f"large_drawdown_probability_{months}m"] * 0.18)
    output["drawdown_risk_score"] = (100 * output["large_drawdown_probability_12m"]).clip(0, 100)
    output["drawdown_model_confidence"] = np.where(output["large_drawdown_probability_12m"] > 0.30, 0.78, 0.68)
    return output
