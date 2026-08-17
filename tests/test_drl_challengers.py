from __future__ import annotations

import numpy as np
import pandas as pd

from src.drl.challengers import run_regional_challengers
from src.drl.regional_ppo import REGIONAL_FEATURES, REGIONAL_SLEEVES


def _panel() -> pd.DataFrame:
    rows = []
    dates = pd.date_range('2022-01-31', periods=96, freq='ME')
    for date_index, date in enumerate(dates):
        for sleeve_index, sleeve in enumerate(REGIONAL_SLEEVES):
            cycle = np.sin((date_index + sleeve_index) / 6.0)
            row = {
                'date': date,
                'sleeve': sleeve,
                'baseline_weight': 0.14,
                'forward_return': 0.004 + 0.003 * cycle,
                'holding_count': 10,
            }
            for feature_index, feature in enumerate(REGIONAL_FEATURES):
                row[feature] = cycle + feature_index * 0.01
            rows.append(row)
    return pd.DataFrame(rows)


def test_simple_challengers_select_parameters_on_validation_only():
    comparison, paths = run_regional_challengers(
        _panel(),
        {
            'max_delta_weight': 0.01,
            'maximum_turnover': 0.10,
            'max_region_weight': 0.40,
            'cash_floor': 0.0,
        },
        {
            'train_fraction': 0.58,
            'validation_fraction': 0.19,
            'embargo_periods': 1,
            'frozen_test_start': '2028-01-31',
            'frozen_test_end': '2028-12-31',
            'minimum_train_periods': 48,
            'minimum_validation_periods': 12,
            'minimum_test_periods': 12,
            'no_trade_band_weight': 0.0,
            'market_friction': {},
            'algorithms': {
                'contextual_bandit': {'ridge_penalties': [0.1, 1.0]},
                'convex_residual': {
                    'risk_aversion_values': [1.0, 3.0],
                    'turnover_penalty': 2.0,
                    'cost_penalty': 0.02,
                },
            },
        },
    )

    assert set(comparison['algorithm']) == {
        'contextual_bandit',
        'convex_residual',
    }
    assert not comparison['test_period_model_selection_used'].any()
    assert comparison.loc[
        comparison['split'].eq('legacy_locked_oos'), 'observations'
    ].eq(12).all()
    assert comparison.groupby('algorithm')['selected_parameter_by_validation'].any().all()
    assert set(paths['split']) == {'validation', 'legacy_locked_oos'}
    assert paths.loc[
        paths['split'].eq('legacy_locked_oos'), 'date'
    ].min() == pd.Timestamp('2028-01-31')
