from __future__ import annotations

from dataclasses import replace
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.models.supervised_alpha import (
    SupervisedAlphaSettings,
    apply_governed_supervised_alpha_overlay,
    build_supervised_alpha_dataset,
    evaluate_predictions,
    expanding_purged_folds,
    run_supervised_alpha_research,
)


def _observed_panel(periods: int = 48, securities: int = 36) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(7)
    dates = pd.date_range('2020-01-31', periods=periods, freq='ME')
    feature_rows = []
    outcome_rows = []
    for date_index, date in enumerate(dates):
        for security_index in range(securities):
            security_id = f'S{security_index:03d}'
            region = 'US' if security_index % 2 == 0 else 'DACH'
            sector = 'Technology' if security_index % 3 == 0 else 'Industrials'
            momentum = (security_index / securities) - 0.5 + 0.05 * np.sin(date_index)
            feature_rows.append(
                {
                    'security_id': security_id,
                    'ticker': security_id,
                    'company_name': f'Company {security_index}',
                    'as_of_date': date,
                    'region': region,
                    'sector': sector,
                    'country': 'United States' if region == 'US' else 'Germany',
                    'currency': 'USD' if region == 'US' else 'EUR',
                    'momentum_6m': momentum,
                    'valuation_score': 50 + 20 * momentum,
                    'cash_flow_quality_score': 55 + 10 * momentum,
                    'average_daily_value_usd': 20_000_000.0,
                    'market_cap_usd': 2_000_000_000.0 + security_index * 1_000_000.0,
                    'fundamentals_available_from': date - pd.Timedelta(days=5),
                    'price_feature_end_date': date,
                    'evidence_mode': 'test_observed',
                }
            )
            realised = 0.04 * momentum + rng.normal(0.0, 0.01)
            outcome_rows.append(
                {
                    'security_id': security_id,
                    'ticker': security_id,
                    'as_of_date': date,
                    'horizon': '3M',
                    'horizon_months': 3,
                    'target_date': date + pd.DateOffset(months=3),
                    'outcome_date': date + pd.DateOffset(months=3),
                    'realised_return': realised,
                }
            )
    return pd.DataFrame(feature_rows), pd.DataFrame(outcome_rows)


def _settings(tmp_path: Path) -> SupervisedAlphaSettings:
    return SupervisedAlphaSettings(
        output_directory=tmp_path / 'reports',
        model_directory=tmp_path / 'models',
        checkpoint_directory=tmp_path / 'checkpoints',
        horizons_months=(3,),
        validation_start=pd.Timestamp('2022-01-31'),
        validation_end=pd.Timestamp('2022-06-30'),
        frozen_test_start=pd.Timestamp('2022-08-31'),
        frozen_test_end=pd.Timestamp('2022-12-31'),
        prospective_holdout_start=pd.Timestamp('2025-01-31'),
        cv_test_periods=2,
        minimum_train_periods=12,
        minimum_test_securities=20,
        primary_horizon_months=3,
        categorical_min_frequency=2,
        ols_minimum_features=2,
        ols_maximum_features=4,
        bootstrap_samples=100,
        minimum_oos_periods=3,
        enabled_families=('ols_screened', 'ridge'),
        model_grids={
            'ols_screened': ({},),
            'ridge': ({'alpha': 1.0}, {'alpha': 10.0}),
        },
    )


def test_expanding_folds_purge_unavailable_labels(tmp_path: Path):
    features, outcomes = _observed_panel()
    settings = _settings(tmp_path)
    dataset, _, _ = build_supervised_alpha_dataset(features, outcomes, settings)
    folds = expanding_purged_folds(dataset, settings)
    assert folds
    for _, train_index, test_index in folds:
        assert dataset.loc[train_index, 'target_date'].max() < dataset.loc[test_index, 'as_of_date'].min()
        assert dataset.loc[test_index, 'target_date'].max() < settings.frozen_test_start


def test_forward_cohorts_are_not_counted_as_independent_months(tmp_path: Path):
    settings = replace(
        _settings(tmp_path),
        minimum_test_securities=5,
        bootstrap_samples=100,
    )
    rows = []
    for date_index, date in enumerate(pd.date_range('2025-01-31', periods=8, freq='ME')):
        for security_index in range(10):
            rows.append(
                {
                    'security_id': f'S{security_index:02d}',
                    'as_of_date': date,
                    'target_date': date + pd.DateOffset(months=6),
                    'horizon_months': 6,
                    'region': 'US',
                    'prediction': float(security_index),
                    'target_excess_return': 0.01 * security_index,
                    'estimated_one_way_cost_bps': 10.0,
                }
            )
    summary, _ = evaluate_predictions(
        pd.DataFrame(rows),
        settings,
        horizon_months=6,
    )
    assert summary['observations'] == 8
    assert summary['independent_observations'] == 2
    assert np.isnan(summary['active_return_ci_lower_95'])
    assert np.isnan(summary['active_sharpe'])
    assert summary['annualised_bank_fee_drag'] == pytest.approx(0.0025)
    assert summary['initial_funding_turnover'] == pytest.approx(0.5)


def test_recurring_turnover_is_capped_before_outcomes_are_scored(tmp_path: Path):
    settings = replace(_settings(tmp_path), minimum_test_securities=5)
    rows = []
    dates = pd.date_range('2025-01-31', periods=5, freq='ME')
    for date_index, date in enumerate(dates):
        for security_index in range(20):
            direction = 1 if date_index % 2 == 0 else -1
            rows.append(
                {
                    'security_id': f'S{security_index:02d}',
                    'as_of_date': date,
                    'target_date': date + pd.DateOffset(months=3),
                    'horizon_months': 3,
                    'region': 'US',
                    'prediction': float(direction * security_index),
                    'target_excess_return': 0.01 * security_index,
                    'estimated_one_way_cost_bps': 10.0,
                }
            )
    summary, monthly = evaluate_predictions(
        pd.DataFrame(rows),
        settings,
        horizon_months=3,
    )
    recurring = monthly.loc[~monthly['is_initial_funding']]
    assert recurring['turnover'].max() <= settings.annual_turnover_budget / 12.0 + 1e-12
    assert summary['annualised_turnover'] <= settings.maximum_annual_turnover + 1e-12


def test_incomplete_outcome_cross_sections_are_excluded(tmp_path: Path):
    features, outcomes = _observed_panel(periods=24, securities=36)
    last_date = outcomes['as_of_date'].max()
    incomplete = outcomes.loc[
        ~(
            outcomes['as_of_date'].eq(last_date)
            & outcomes['security_id'].str[1:].astype(int).ge(18)
        )
    ].copy()
    dataset, _, _ = build_supervised_alpha_dataset(
        features,
        incomplete,
        _settings(tmp_path),
    )
    assert last_date not in set(dataset['as_of_date'])
    assert dataset['outcome_cross_section_coverage'].ge(0.90).all()


def test_rejected_overlay_does_not_change_expected_returns(tmp_path: Path):
    settings = _settings(tmp_path)
    optimiser = pd.DataFrame(
        {
            'security_id': ['S1', 'S2'],
            'region': ['US', 'US'],
            'market_cap_usd': [2.0, 1.0],
            'expected_total_return_12m': [0.08, 0.04],
        }
    )
    predictions = pd.DataFrame(
        {
            'security_id': ['S1', 'S2'],
            'horizon_months': [3, 3],
            'predicted_benchmark_relative_return': [0.05, -0.05],
            'cost_adjusted_predicted_excess_return': [0.04, -0.06],
            'supervised_alpha_score': [90.0, 10.0],
            'no_trade_recommended': [False, False],
        }
    )
    decision = pd.DataFrame(
        [{'scope': 'overall', 'status': 'REJECTED', 'deployment_blend_weight': 0.0}]
    )
    result = apply_governed_supervised_alpha_overlay(
        optimiser,
        predictions,
        decision,
        settings,
    )
    np.testing.assert_allclose(
        result['expected_total_return_12m'],
        optimiser['expected_total_return_12m'],
    )


def test_small_supervised_alpha_research_run(tmp_path: Path):
    features, outcomes = _observed_panel()
    settings = _settings(tmp_path)
    latest = features.loc[features['as_of_date'].eq(features['as_of_date'].max())].copy()
    latest['current_weight'] = 0.0
    latest['expected_total_return_3m'] = 0.02
    result = run_supervised_alpha_research(
        features,
        outcomes,
        latest,
        settings,
    )
    assert not result.validation_summary.empty
    assert 'supervised_alpha_ensemble' in set(result.validation_summary['candidate'])
    assert not result.oos_summary.empty
    assert not result.latest_predictions.empty
    assert set(result.quantile_metrics['calibration_method']) == {
        'purged_date_block_conformal'
    }
    assert set(result.quantile_metrics['calibration_target_coverage']) == {0.95}
    overall = result.acceptance_decision.loc[
        result.acceptance_decision['scope'].eq('overall')
    ].iloc[0]
    assert overall['deployment_blend_weight'] == 0.0
    assert 'legacy_oos_exposed_to_research_iteration' in overall['reasons']
    assert (tmp_path / 'models' / 'supervised_alpha_3m.joblib').exists()


@pytest.mark.skipif(importlib.util.find_spec('xgboost') is None, reason='optional xgboost extra')
def test_xgboost_regression_and_ranking_challengers(tmp_path: Path):
    features, outcomes = _observed_panel()
    settings = replace(
        _settings(tmp_path),
        enabled_families=('xgboost', 'xgb_ranker'),
        model_grids={
            'xgboost': (
                {
                    'learning_rate': 0.05,
                    'n_estimators': 30,
                    'max_depth': 2,
                    'min_child_weight': 10.0,
                    'reg_lambda': 10.0,
                },
            ),
            'xgb_ranker': (
                {
                    'learning_rate': 0.05,
                    'n_estimators': 30,
                    'max_depth': 2,
                    'min_child_weight': 10.0,
                    'reg_lambda': 10.0,
                },
            ),
        },
    )
    latest = features.loc[features['as_of_date'].eq(features['as_of_date'].max())].copy()
    latest['current_weight'] = 0.0
    latest['expected_total_return_3m'] = 0.02
    result = run_supervised_alpha_research(features, outcomes, latest, settings)
    assert {'xgboost', 'xgb_ranker'}.issubset(set(result.validation_summary['family']))
    assert result.failures.empty
