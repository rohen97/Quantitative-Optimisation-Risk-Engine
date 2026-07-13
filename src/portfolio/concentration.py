from __future__ import annotations

import pandas as pd


def hhi(weights: pd.Series) -> float:
    return float((weights.astype(float) ** 2).sum())


def effective_number_of_holdings(weights: pd.Series) -> float:
    value = hhi(weights)
    return float(1 / value) if value > 0 else 0.0


def top_concentration(weights: pd.Series, n: int) -> float:
    return float(weights.sort_values(ascending=False).head(n).sum())


def concentration_summary(weights: pd.Series) -> dict[str, float]:
    """Calculate headline concentration metrics from position weights."""
    return {
        "top_1_concentration": top_concentration(weights, 1),
        "top_3_concentration": top_concentration(weights, 3),
        "top_5_concentration": top_concentration(weights, 5),
        "hhi": hhi(weights),
        "effective_number_of_holdings": effective_number_of_holdings(weights),
    }
