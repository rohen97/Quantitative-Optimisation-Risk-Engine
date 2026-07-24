from __future__ import annotations

import pandas as pd


DEFAULT_COMPONENTS = (
    "sentiment", "alternative_data", "narrative_reframing", "regime_features",
    "distributional_forecasts", "dividend_features", "quality_features",
    "tail_risk_constraints", "transaction_costs", "chaos_gating", "drl_overlay",
)


def build_ablation_report(full_metrics: dict[str, float], ablated_metrics: dict[str, dict[str, float]]) -> pd.DataFrame:
    rows = []
    for component in DEFAULT_COMPONENTS:
        metrics = ablated_metrics.get(component)
        if metrics is None:
            rows.append({"component_removed": component, "status": "NOT_EVALUATED", "notes": "No historical ablation evidence available."})
            continue
        row = {"component_removed": component, "status": "EVALUATED"}
        row.update({f"{name}_change": value - full_metrics.get(name, 0.0) for name, value in metrics.items()})
        rows.append(row)
    return pd.DataFrame(rows)
