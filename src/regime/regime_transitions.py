from __future__ import annotations

import pandas as pd


def build_regime_transition_matrix(
    factor_lens: pd.DataFrame,
    factor_probabilities: pd.DataFrame,
    chaos_probabilities: pd.DataFrame,
    fused_regime: str | None = None,
    window_days: int = 180,
) -> pd.DataFrame:
    """Build simple historical transition matrices for factor, chaos and fused regimes."""
    sequence = []
    recent = factor_lens[factor_lens["region"].eq("Global")].sort_values("date").tail(24)
    for row in recent.itertuples():
        if row.credit_proxy > 0.012:
            sequence.append("crisis")
        elif row.inflation_proxy > 0.008:
            sequence.append("inflation")
        elif row.momentum_factor > 0.006 and row.credit_proxy > 0:
            sequence.append("walking_on_ice")
        else:
            sequence.append("steady_state")
    rows = []
    counts: dict[tuple[str, str], int] = {}
    for left, right in zip(sequence, sequence[1:]):
        counts[(left, right)] = counts.get((left, right), 0) + 1
    totals: dict[str, int] = {}
    for left, right in counts:
        totals[left] = totals.get(left, 0) + counts[(left, right)]
    for (left, right), count in counts.items():
        rows.append({"regime_type": "factor", "from_regime": left, "to_regime": right, "transition_probability": count / totals[left], "transition_count": count, "window_days": window_days})
    chaos_state = chaos_probabilities.iloc[0]["dominant_chaos_regime"]
    rows.append({"regime_type": "chaos", "from_regime": chaos_state, "to_regime": chaos_state, "transition_probability": 1.0, "transition_count": 1, "window_days": window_days})
    if fused_regime:
        rows.append({"regime_type": "fused", "from_regime": fused_regime, "to_regime": fused_regime, "transition_probability": 1.0, "transition_count": 1, "window_days": window_days})
    output = pd.DataFrame(rows)
    output["regime_persistence_score"] = output["transition_probability"] * 100
    output["regime_switch_probability"] = 1 - output["transition_probability"]
    output["regime_deterioration_transition_probability"] = output["to_regime"].isin(["crisis", "credit_stress", "high_chaos", "crisis_high_chaos"]).astype(float) * output["transition_probability"]
    return output
