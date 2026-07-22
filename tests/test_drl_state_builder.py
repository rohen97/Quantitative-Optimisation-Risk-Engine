import numpy as np
import pandas as pd

from src.data_ingestion.universe import build_universe
from src.drl.state_builder import build_drl_state, build_state_schema


def test_drl_state_builder_is_finite_and_ordered():
    assets = ["AAA", "BBB"]
    cross = pd.DataFrame(
        {
            "ticker": assets,
            "final_recommendation_score": [80, 60],
            "expected_total_return_12m": [0.08, 0.04],
            "liquidity_score": [70, 55],
        }
    )
    state = build_drl_state(
        pd.Timestamp("2026-01-31"),
        assets,
        np.array([0.4, 0.3]),
        np.array([0.45, 0.35]),
        pd.DataFrame({"ticker": assets, "volatility_60d": [0.18, 0.22]}),
        cross,
        {"cash_weight": 0.2, "nav": 1_000_000, "turnover_limit": 0.2},
        np.array([True, False]),
    )
    assert state.observation.shape[0] == 3
    assert state.asset_ids[-1] == "CASH"
    assert np.isfinite(state.observation).all()
    assert build_state_schema(state.feature_names)["feature_order"].is_monotonic_increasing


def test_drl_state_excludes_future_targets_preserves_mask_and_cash_and_universe_scope():
    universe = build_universe()
    assert "India" not in set(universe["country"])

    assets = ["AAA", "BBB"]
    state = build_drl_state(
        pd.Timestamp("2026-01-31"),
        assets,
        np.array([0.25, 0.50]),
        np.array([0.30, 0.45]),
        pd.DataFrame({"ticker": assets, "realized_future_return_12m": [9.0, 9.0]}),
        pd.DataFrame({"ticker": assets, "target_return_label": [1.0, 0.0], "expected_total_return_12m": [0.06, 0.04]}),
        {"cash_weight": 0.25, "nav": 1_000_000},
        np.array([True, False]),
    )

    forbidden_tokens = ("future", "target_return", "label", "realized")
    assert not any(any(token in feature for token in forbidden_tokens) for feature in state.feature_names)
    assert state.eligibility_mask.tolist() == [True, False, True]
    assert state.asset_ids[-1] == "CASH"
    assert state.cash_index == 2
