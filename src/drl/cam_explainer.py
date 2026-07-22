from __future__ import annotations

import numpy as np
import pandas as pd


def build_cam_metadata() -> pd.DataFrame:
    """Document future CAM-compatible explanation layer interfaces."""
    return pd.DataFrame(
        [
            {
                "component": "temporal_encoder",
                "method": "TCN with causal and dilated convolutions",
                "status": "interface_ready",
            },
            {
                "component": "class_activation_mapping",
                "method": "asset-time activation map over allocation logits",
                "status": "placeholder_in_mvp",
            },
        ]
    )


def build_asset_time_attribution_map(
    asset_data: pd.DataFrame,
    target_weights,
    lookback_days: int = 60,
    as_of_date: pd.Timestamp | None = None,
    material_weight_threshold: float = 0.0025,
) -> pd.DataFrame:
    """Build deterministic CAM-compatible asset-time attribution rows.

    These are model attributions for the MVP scaffold, not causal claims.
    """
    as_of = pd.Timestamp(as_of_date or pd.Timestamp.today().normalize())
    data = asset_data.reset_index(drop=True).copy()
    weights = np.asarray(target_weights, dtype=float)
    rows = []
    for target_idx, target in data.iterrows():
        target_weight = float(weights[target_idx]) if target_idx < len(weights) else 0.0
        if target_weight < material_weight_threshold:
            continue
        for source_idx, source in data.iterrows():
            source_weight = float(weights[source_idx]) if source_idx < len(weights) else 0.0
            relation = abs(target_weight - source_weight) + 0.01 * (1 + (target_idx == source_idx))
            for step in range(1, int(lookback_days) + 1):
                score = relation * (lookback_days - step + 1) / max(lookback_days, 1)
                rows.append(
                    {
                        "as_of_date": as_of.date().isoformat(),
                        "target_security_id": target.get("security_id", target.get("ticker", f"target_{target_idx}")),
                        "target_ticker": target.get("ticker", f"target_{target_idx}"),
                        "influencing_security_id": source.get("security_id", source.get("ticker", f"source_{source_idx}")),
                        "influencing_ticker": source.get("ticker", f"source_{source_idx}"),
                        "lookback_step": step,
                        "lookback_date": (as_of - pd.Timedelta(days=step)).date().isoformat(),
                        "attribution_score": float(score),
                    }
                )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "as_of_date",
                "target_security_id",
                "target_ticker",
                "influencing_security_id",
                "influencing_ticker",
                "lookback_step",
                "lookback_date",
                "attribution_score",
                "attribution_rank",
            ]
        )
    frame["attribution_rank"] = frame.groupby(["target_ticker"])["attribution_score"].rank(ascending=False, method="first").astype(int)
    return frame.sort_values(["target_ticker", "attribution_rank"]).reset_index(drop=True)
