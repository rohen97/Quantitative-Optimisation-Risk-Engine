import json
from dataclasses import replace

import pandas as pd
import pytest

from src.validation.data_loader import load_validation_data
from src.validation.governance import make_governance_decision
from src.validation.walk_forward import (
    _PriceMatcher,
    _risk_rows,
    build_realised_outcomes,
    load_walk_forward_config,
    reconstruct_statement_availability,
)


def test_yahoo_retrieval_date_is_reconstructed_with_reporting_lag():
    statements = pd.DataFrame(
        {
            'security_id': ['A'],
            'fiscal_period_end': ['2021-12-31'],
            'filing_date': ['2026-08-07'],
            'source': ['yahoo_finance_timeseries'],
        }
    )
    result = reconstruct_statement_availability(statements, 120)
    assert result.loc[0, 'reconstructed_available_from'] == pd.Timestamp('2022-04-30')
    assert result.loc[0, 'availability_basis'] == 'fiscal_period_end_plus_120d'


def test_observed_sec_acceptance_takes_precedence_over_proxy_dates():
    statements = pd.DataFrame(
        {
            'security_id': ['A'],
            'fiscal_period_end': ['2021-12-31'],
            'filing_date': ['2022-03-10'],
            'observed_acceptance_datetime': ['2022-02-28T18:30:00Z'],
            'source': ['nasdaq_mergent_f1'],
        }
    )
    result = reconstruct_statement_availability(statements, 120)
    assert result.loc[0, 'reconstructed_available_from'] == pd.Timestamp(
        '2022-02-28 18:30:00'
    )
    assert result.loc[0, 'availability_basis'] == 'observed_sec_acceptance_datetime'


def test_realised_outcome_uses_next_trading_day_after_target():
    prices = pd.DataFrame(
        {
            'security_id': ['A', 'A', 'A'],
            'ticker': ['A', 'A', 'A'],
            'trade_date': pd.to_datetime(
                ['2024-01-31', '2024-04-29', '2024-05-01']
            ),
            'adjusted_close': [100.0, 108.0, 110.0],
            'close_price': [100.0, 108.0, 110.0],
            'return': [0.0, 0.08, 0.0185],
            'return_outlier_flag': [False, False, False],
        }
    )
    forecasts = pd.DataFrame(
        {
            'security_id': ['A'],
            'ticker': ['A'],
            'as_of_date': [pd.Timestamp('2024-01-31')],
            'horizon': ['3M'],
            'horizon_months': [3],
        }
    )
    outcome = build_realised_outcomes(forecasts, _PriceMatcher(prices), 7)
    assert outcome.loc[0, 'target_date'] == pd.Timestamp('2024-04-30')
    assert outcome.loc[0, 'end_trade_date'] == pd.Timestamp('2024-05-01')
    assert outcome.loc[0, 'realised_return'] == pytest.approx(0.10)


def test_realised_outcome_allows_extended_exchange_holiday_gap():
    prices = pd.DataFrame(
        {
            'security_id': ['A', 'A'],
            'ticker': ['A', 'A'],
            'trade_date': pd.to_datetime(['2023-08-31', '2023-10-09']),
            'adjusted_close': [100.0, 105.0],
            'close_price': [100.0, 105.0],
            'return': [0.0, 0.05],
            'return_outlier_flag': [False, False],
        }
    )
    forecasts = pd.DataFrame(
        {
            'security_id': ['A'],
            'ticker': ['A'],
            'as_of_date': [pd.Timestamp('2023-08-31')],
            'horizon': ['1M'],
            'horizon_months': [1],
        }
    )

    outcome = build_realised_outcomes(forecasts, _PriceMatcher(prices), 14)

    assert outcome.loc[0, 'target_date'] == pd.Timestamp('2023-09-30')
    assert outcome.loc[0, 'end_trade_date'] == pd.Timestamp('2023-10-09')
    assert outcome.loc[0, 'realised_return'] == pytest.approx(0.05)


def test_validation_loader_prefers_walk_forward_artifacts(tmp_path):
    directory = tmp_path / 'walk_forward'
    directory.mkdir()
    forecast = pd.DataFrame(
        {
            'security_id': ['A'],
            'ticker': ['A'],
            'as_of_date': [pd.Timestamp('2024-01-31')],
            'horizon': ['3M'],
            'expected_total_return': [0.05],
        }
    )
    outcome = pd.DataFrame(
        {
            'security_id': ['A'],
            'ticker': ['A'],
            'as_of_date': [pd.Timestamp('2024-01-31')],
            'horizon': ['3M'],
            'realised_return': [0.04],
        }
    )
    forecast.to_parquet(directory / 'historical_forecasts.parquet', index=False)
    outcome.to_parquet(directory / 'historical_realised_outcomes.parquet', index=False)
    (directory / 'walk_forward_manifest.json').write_text(
        json.dumps(
            {
                'evidence_mode': 'reconstructed_pit_proxy',
                'limitations': [],
            }
        ),
        encoding='utf-8',
    )
    package = load_validation_data(
        'test',
        pd.Timestamp('2026-08-07'),
        output_root=tmp_path,
    )
    assert package.evidence_mode == 'reconstructed_pit_proxy'
    assert list(package.forecasts) == ['3M']
    assert len(package.realised_returns) == 1


def test_reconstructed_evidence_caps_approval_at_conditional():
    decision = make_governance_decision(
        {'component': 100.0},
        [],
        [],
        approval_threshold=70.0,
        conditional_threshold=60.0,
        maximum_status='CONDITIONALLY_APPROVED',
    )
    assert decision.status == 'CONDITIONALLY_APPROVED'


def test_daily_ewma_risk_forecast_uses_only_prior_returns():
    dates = pd.bdate_range('2023-11-01', periods=190)
    anchor = dates[160]
    returns = pd.Series(0.001, index=dates)
    returns.loc[dates[161]] = -0.10
    prices = pd.DataFrame(
        {
            'security_id': 'A',
            'trade_date': dates,
            'return': returns.to_numpy(),
        }
    )
    portfolio = pd.DataFrame({'security_id': ['A'], 'weight': [1.0]})
    config = replace(
        load_walk_forward_config(),
        risk_lookback_rows=150,
        risk_ewma_decay=0.94,
        risk_candidate_models=('ewma_normal',),
    )
    result = _risk_rows(portfolio, anchor, _PriceMatcher(prices), config)

    assert result['training_end_date'].lt(result['date']).all()
    assert result.loc[1, 'training_end_date'] == result.loc[0, 'date']
    assert result.loc[1, 'forecast_volatility'] > result.loc[0, 'forecast_volatility']
    assert result['risk_model'].eq('daily_ewma_normal').all()
    assert bool(result.loc[0, 'risk_exception_triggered'])
    assert bool(result.loc[1, 'risk_exception_response_active'])
    assert result.loc[1, 'risk_effective_scale_factor'] == pytest.approx(1.10)
