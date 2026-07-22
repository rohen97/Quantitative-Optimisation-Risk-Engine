from __future__ import annotations

import numpy as np
import pandas as pd


def evaluate_portfolio(asset_data: pd.DataFrame, weights: np.ndarray, label: str) -> dict[str, float | str]:
    """Evaluate expected net performance and conservative risk proxies."""
    w = np.asarray(weights, dtype=float)
    return {
        "portfolio": label,
        "expected_total_return": float((w * asset_data["expected_total_return_12m"].fillna(0.0)).sum()),
        "expected_dividend_yield": float((w * asset_data["expected_dividend_return_12m"].fillna(0.0)).sum()),
        "expected_volatility": float((w * asset_data["expected_volatility_12m"].fillna(0.20)).sum()),
        "cvar_5": float((w * asset_data["cvar_5_12m"].fillna(-0.25)).sum()),
        "expected_shortfall_5": float((w * asset_data["expected_shortfall_5_12m"].fillna(-0.25)).sum()),
        "drawdown_probability": float((w * asset_data["large_drawdown_probability_12m"].fillna(0.20)).sum()),
        "dividend_cut_probability": float((w * asset_data["dividend_cut_probability"].fillna(0.10)).sum()),
        "hhi": float(np.square(w).sum()),
        "effective_number_of_holdings": float(1 / max(np.square(w).sum(), 1e-12)),
    }


def build_backtest_results(asset_data: pd.DataFrame, baseline_weights: np.ndarray, drl_weights: np.ndarray) -> pd.DataFrame:
    """Create a deterministic mock backtest comparison for the overlay."""
    baseline = evaluate_portfolio(asset_data, baseline_weights, "baseline_classical_optimiser")
    drl = evaluate_portfolio(asset_data, drl_weights, "constrained_regime_gated_drl")
    rows = []
    for window, multiplier in [("train", 0.98), ("validation", 0.99), ("test", 1.0), ("worst_window", 0.85)]:
        for row in [baseline, drl]:
            adjusted = row.copy()
            adjusted["window"] = window
            adjusted["net_risk_adjusted_return"] = (
                float(row["expected_total_return"]) + float(row["expected_dividend_yield"]) + float(row["cvar_5"])
            ) * multiplier
            rows.append(adjusted)
    return pd.DataFrame(rows)
