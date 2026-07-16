from __future__ import annotations

from dataclasses import dataclass
import json

import pandas as pd


@dataclass
class ModelRegistryEntry:
    name: str
    version: str
    description: str


def build_model_registry(metrics_by_horizon: dict[int, dict[str, float]]) -> pd.DataFrame:
    """Create an upgradeable registry table for the deterministic ML baseline."""
    rows = []
    created_at = pd.Timestamp.today().normalize()
    for horizon, metrics in metrics_by_horizon.items():
        rows.append(
            {
                "model_name": "wolf_deterministic_distribution_forecaster",
                "model_type": "deterministic_mock_baseline",
                "target": f"forward_total_return_{horizon}m",
                "horizon": horizon,
                "feature_set": "quality_income_valuation_risk_liquidity_sentiment_narrative_regime_portfolio",
                "training_start_date": "",
                "training_end_date": "",
                "validation_start_date": "",
                "validation_end_date": "",
                "metrics": json.dumps(metrics, sort_keys=True),
                "model_version": "v0.1-mock",
                "created_at": created_at,
            }
        )
    return pd.DataFrame(rows)
