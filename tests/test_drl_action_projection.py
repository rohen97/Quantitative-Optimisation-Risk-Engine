import numpy as np
import pandas as pd

from src.drl.action_projection import bounded_residual_action, project_to_feasible_set, project_weights


def _metadata():
    return pd.DataFrame(
        {
            "ticker": ["AAA", "BBB", "CCC", "CASH"],
            "sector": ["Tech", "Tech", "Health", "Cash"],
            "country": ["DE", "FR", "GB", "Cash"],
            "region": ["DACH", "EU", "UK", "Cash"],
            "currency": ["EUR", "EUR", "GBP", "USD"],
            "asset_class": ["equity", "equity", "equity", "cash"],
            "average_daily_value_usd": [20_000_000, 20_000_000, 10_000_000, 1_000_000_000],
        }
    )


def test_bounded_residual_action_clips_monthly_delta():
    action = bounded_residual_action(np.array([0.03, -0.05, 0.005]), 0.01)
    assert np.allclose(action, np.array([0.01, -0.01, 0.005]))


def test_project_weights_enforces_exclusion_cash_and_turnover():
    result = project_weights(
        np.array([0.30, 0.00, 0.65, 0.05]),
        np.array([0.02, -0.02, 0.02, 0.0]),
        np.array([True, False, True, True]),
        _metadata(),
        np.array([0.30, 0.00, 0.65, 0.05]),
        {
            "max_delta_weight": 0.01,
            "max_single_name_weight": 0.60,
            "maximum_turnover": 0.08,
            "cash_floor": 0.05,
        },
    )
    assert result.projected_weights[1] == 0
    assert result.projected_weights[3] >= 0.05
    assert abs(result.projected_weights.sum() - 1) < 1e-8
    assert result.constraint_adjustments["turnover"] <= 0.08 + 1e-6


def test_project_weights_falls_back_when_infeasible():
    result = project_weights(
        np.array([0.30, 0.30, 0.35, 0.05]),
        np.array([0.02, -0.02, 0.02, 0.0]),
        np.array([True, True, True, True]),
        _metadata(),
        np.array([0.30, 0.30, 0.35, 0.05]),
        {
            "max_delta_weight": 0.02,
            "max_single_name_weight": 0.20,
            "maximum_turnover": 0.01,
            "cash_floor": 0.05,
        },
    )
    assert result.fallback_used
    assert not result.feasible


def test_drl_projection_preserves_hard_exclusions_and_caps():
    data = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB", "CCC"],
            "sector": ["Tech", "Tech", "Health"],
            "country": ["DE", "FR", "GB"],
            "region": ["DACH", "EU", "UK"],
            "currency": ["EUR", "EUR", "GBP"],
        }
    )
    weights, report = project_to_feasible_set(
        np.array([0.4, 0.3, 0.3]),
        np.array([0.02, 0.02, -0.01]),
        data,
        np.array([True, False, True]),
        {"max_single_name_weight": 0.60, "max_drl_adjustment": 0.015},
        cash_weight=0.05,
    )
    assert weights[1] == 0
    assert weights.sum() <= 0.95 + 1e-12
    assert report.loc[report["ticker"].eq("BBB"), "projection_reason"].iloc[0] == "hard_exclusion_zero_weight"


def test_project_weights_respects_name_group_currency_and_turnover_caps():
    meta = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB", "CCC", "DDD", "CASH"],
            "sector": ["Tech", "Tech", "Health", "Utilities", "Cash"],
            "country": ["DE", "DE", "FR", "GB", "Cash"],
            "region": ["DACH", "DACH", "EU", "UK", "Cash"],
            "currency": ["EUR", "EUR", "EUR", "GBP", "USD"],
            "asset_class": ["equity", "equity", "equity", "equity", "cash"],
            "average_daily_value_usd": [50_000_000, 50_000_000, 50_000_000, 50_000_000, 1_000_000_000],
        }
    )
    current = np.array([0.20, 0.20, 0.20, 0.20, 0.20])
    result = project_weights(
        current,
        np.array([0.20, 0.20, 0.20, -0.10, 0.0]),
        np.array([True, True, True, False, True]),
        meta,
        current,
        {
            "max_delta_weight": 0.25,
            "max_single_name_weight": 0.25,
            "max_sector_weight": 0.40,
            "max_country_weight": 0.40,
            "max_currency_weight": 0.60,
            "maximum_turnover": 0.50,
            "cash_floor": 0.15,
        },
    )
    weights = result.projected_weights
    assert np.all(weights >= -1e-12)
    assert abs(weights.sum() - 1.0) < 1e-8
    assert weights[3] == 0
    assert weights[:4].max() <= 0.25 + 1e-8
    assert weights[[0, 1]].sum() <= 0.40 + 1e-8
    assert weights[[0, 1]].sum() <= 0.40 + 1e-8
    assert weights[[0, 1, 2]].sum() <= 0.60 + 1e-8
    assert np.abs(weights - current).sum() <= 0.50 + 1e-8


def test_project_weights_enforces_cash_ceiling():
    result = project_weights(
        np.array([0.20, 0.20, 0.40, 0.20]),
        np.array([-0.20, -0.20, -0.20, 0.20]),
        np.array([True, True, True, True]),
        _metadata(),
        np.array([0.20, 0.20, 0.40, 0.20]),
        {
            "max_delta_weight": 0.20,
            "max_single_name_weight": 0.50,
            "maximum_turnover": 1.0,
            "cash_floor": 0.10,
            "maximum_cash_weight": 0.25,
        },
    )
    assert result.feasible
    assert result.projected_weights[-1] <= 0.25 + 1e-8
