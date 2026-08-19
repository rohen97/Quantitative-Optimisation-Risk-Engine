import numpy as np
import pandas as pd

from src.validation.historical_evaluation import _evaluate_risk


def test_risk_evaluation_reports_chronological_holdout_separately():
    rng = np.random.default_rng(21)
    observations = 700
    frame = pd.DataFrame(
        {
            'date': pd.bdate_range('2022-01-03', periods=observations),
            'realised_return': rng.normal(0.0, 0.01, observations),
            'var_95': np.full(observations, -0.01645),
            'var_99': np.full(observations, -0.02330),
            'expected_shortfall_95': np.full(observations, -0.0206),
            'expected_shortfall_99': np.full(observations, -0.0267),
        }
    )
    result, status = _evaluate_risk(
        frame,
        {
            'violation_rate_tolerance': 1.0,
            'kupiec_pvalue_threshold': 0.0,
            'christoffersen_pvalue_threshold': 0.0,
            'chronological_holdout_fraction': 0.40,
            'minimum_holdout_observations': 252,
        },
    )
    assert set(result['evaluation_segment']) == {
        'overall',
        'chronological_holdout',
    }
    assert set(result['confidence_level']) == {0.95, 0.99}
    assert (
        result.loc[
            result['evaluation_segment'].eq('chronological_holdout'),
            'observations',
        ]
        == 280
    ).all()
    assert result.loc[
        result['evaluation_segment'].eq('chronological_holdout'),
        'governance_gate',
    ].all()
    assert not result.loc[
        result['evaluation_segment'].eq('overall'),
        'governance_gate',
    ].any()
    assert status == 'PASS'
