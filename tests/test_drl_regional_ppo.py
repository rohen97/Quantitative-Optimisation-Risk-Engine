from __future__ import annotations

import numpy as np
import pandas as pd

from src.drl.regional_ppo import (
    REGIONAL_FEATURES,
    REGIONAL_SLEEVES,
    RegionalResidualEnv,
    apply_regional_scaler,
    chronological_regional_split,
    fit_regional_scaler,
    map_regional_overlay_to_assets,
    summarise_regional_path,
)


def _panel(periods: int = 40) -> pd.DataFrame:
    rows = []
    for position, date in enumerate(pd.date_range("2022-01-31", periods=periods, freq="ME")):
        for sleeve_index, sleeve in enumerate(REGIONAL_SLEEVES):
            row = {
                "date": date,
                "sleeve": sleeve,
                "baseline_weight": 0.14,
                "forward_return": 0.005 + sleeve_index * 0.001,
            }
            for feature_index, feature in enumerate(REGIONAL_FEATURES):
                row[feature] = position + sleeve_index + feature_index
            rows.append(row)
    return pd.DataFrame(rows)


def test_regional_split_is_chronological_and_embargoed():
    panel = _panel()
    split = chronological_regional_split(panel["date"].unique(), 0.58, 0.19, 1)
    assert split.train_dates
    assert split.validation_dates
    assert split.test_dates
    assert set(split.train_dates).isdisjoint(split.validation_dates)
    assert set(split.validation_dates).isdisjoint(split.test_dates)
    assert max(split.train_dates) < min(split.validation_dates) < min(split.test_dates)
    assert len(split.embargo_dates) == 2


def test_scaler_fits_training_dates_only():
    panel = _panel()
    train_dates = tuple(sorted(panel["date"].unique())[:20])
    scaler = fit_regional_scaler(panel, train_dates)
    scaled = apply_regional_scaler(panel, scaler)
    training = scaled.loc[scaled["date"].isin(train_dates)]
    assert abs(training[f"state_{REGIONAL_FEATURES[0]}"].mean()) < 1e-10


def test_regional_environment_caps_incremental_turnover():
    panel = _panel(3)
    scaler = fit_regional_scaler(panel, tuple(sorted(panel["date"].unique())[:2]))
    env = RegionalResidualEnv(
        apply_regional_scaler(panel, scaler),
        {
            "max_delta_weight": 0.05,
            "maximum_turnover": 0.03,
            "max_region_weight": 0.40,
            "cash_floor": 0.05,
        },
        {"no_trade_band_weight": 0.0, "market_friction": {}},
    )
    env.reset(seed=1)
    target, overlay, turnover = env.project_action(np.full(len(REGIONAL_SLEEVES), 0.05))
    assert turnover <= 0.03 + 1e-12
    assert target.sum() <= 0.95 + 1e-12
    assert np.all(target >= 0)
    assert np.allclose(target - 0.14, overlay)


def test_regional_overlay_maps_to_names_without_changing_total_active_weight():
    assets = pd.DataFrame(
        {
            "region": ["US", "US", "UK"],
            "eligible_for_optimisation": [True, True, True],
            "final_recommendation_score": [80, 60, 70],
        }
    )
    overlay = np.zeros(len(REGIONAL_SLEEVES))
    overlay[REGIONAL_SLEEVES.index("US")] = 0.02
    overlay[REGIONAL_SLEEVES.index("UK")] = -0.01
    actions = map_regional_overlay_to_assets(
        assets,
        np.array([0.20, 0.10, 0.10]),
        overlay,
    )
    assert np.isclose(actions[:2].sum(), 0.02)
    assert np.isclose(actions[2], -0.01)


def test_oos_metrics_use_monthly_path_not_scalar_reward():
    path = pd.DataFrame(
        {
            "net_return": [0.01, -0.005, 0.02, 0.0],
            "baseline_return": [0.008, -0.004, 0.015, 0.0],
            "active_return": [0.002, -0.001, 0.005, 0.0],
            "incremental_turnover": [0.02, 0.01, 0.03, 0.0],
            "transaction_cost": [0.0001] * 4,
            "constraint_violations": [0] * 4,
        }
    )
    metrics = summarise_regional_path(path)
    assert metrics["observations"] == 4
    assert np.isfinite(metrics["net_sharpe"])
    assert metrics["annualised_incremental_turnover"] == 0.18
