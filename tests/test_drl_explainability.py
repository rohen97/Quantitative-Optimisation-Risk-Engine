import numpy as np
import pandas as pd

from src.drl.explainability import (
    asset_time_attributions,
    build_constraint_adjustment_explanations,
    explain_weight_changes,
    feature_attributions,
)
from src.drl.state_builder import build_drl_state


def test_drl_explainability_outputs_material_changes_and_features():
    data = pd.DataFrame({"ticker": ["AAA", "BBB"]})
    explanations = explain_weight_changes(data, np.array([0.4, 0.6]), np.array([0.45, 0.55]))
    assert explanations["material_change_flag"].all()
    state = build_drl_state(
        pd.Timestamp("2026-01-31"),
        ["AAA", "BBB"],
        np.array([0.4, 0.6]),
        np.array([0.4, 0.6]),
        pd.DataFrame({"ticker": ["AAA", "BBB"]}),
        pd.DataFrame({"ticker": ["AAA", "BBB"], "final_recommendation_score": [70, 60]}),
        {"cash_weight": 0.0},
        np.array([True, True]),
    )
    attrs = feature_attributions(state, np.array([0.45, 0.55]))
    assert {"ticker", "feature_group", "attribution_score", "rank", "attribution_description"}.issubset(attrs.columns)
    assert "dividend quality" in set(attrs["feature_group"])


def test_asset_time_attributions_have_required_columns():
    data = pd.DataFrame({"security_id": ["A", "B"], "ticker": ["AAA", "BBB"], "target_weight": [0.05, 0.0]})
    attrs = asset_time_attributions(data, np.array([0.05, 0.0]), lookback_days=3)
    assert {
        "as_of_date",
        "target_security_id",
        "target_ticker",
        "influencing_security_id",
        "influencing_ticker",
        "lookback_step",
        "lookback_date",
        "attribution_score",
        "attribution_rank",
    }.issubset(attrs.columns)
    assert set(attrs["target_ticker"]) == {"AAA"}


def test_constraint_adjustment_explanations_use_attribution_safe_language():
    asset_data = pd.DataFrame(
        {
            "security_id": ["A"],
            "ticker": ["AAA"],
            "expected_total_return_12m": [0.08],
            "dividend_safety_score": [80],
            "regime_suitability_score": [75],
            "valuation_score": [40],
        }
    )
    projection = pd.DataFrame(
        {
            "ticker": ["AAA"],
            "baseline_weight": [0.04],
            "raw_action": [0.012],
            "candidate_weight": [0.056],
            "projected_weight": [0.043],
            "eligible_for_drl": [True],
            "eligibility_mask_adjustment": [0.0],
        }
    )
    report = build_constraint_adjustment_explanations(asset_data, projection, throttle_adjustment=0.25)
    text = report.loc[0, "human_readable_explanation"].lower()
    assert "positive drivers" in text
    assert "constraint projection" in text
    for banned in ["caused", "proves", "guarantees"]:
        assert banned not in text
    assert report.loc[0, "raw_drl_residual"] == 0.012
    assert report.loc[0, "final_projected_weight"] == 0.043
