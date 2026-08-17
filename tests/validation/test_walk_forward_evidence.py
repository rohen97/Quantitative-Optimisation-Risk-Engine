import json
from dataclasses import replace

import pandas as pd
import pytest

from src.validation.data_loader import load_validation_data
from src.validation.governance import make_governance_decision
from src.validation.walk_forward import (
    _MarketCapMatcher,
    _PriceMatcher,
    _fundamental_snapshot,
    _risk_rows,
    build_realised_outcomes,
    historical_universe_snapshot,
    load_walk_forward_config,
    reconstruct_statement_availability,
)


def test_historical_universe_includes_inactive_name_only_before_dated_delisting():
    universe = pd.DataFrame(
        {
            'security_id': ['LIVE', 'OLD', 'UNDATED'],
            'listing_status': ['Active', 'Inactive', 'Inactive'],
            'current_listing_status': ['Active', 'Inactive', 'Inactive'],
            'delisting_date': [pd.NaT, pd.Timestamp('2024-06-15'), pd.NaT],
        }
    )
    events = pd.DataFrame(
        {
            'security_id': ['OLD'],
            'event_type': ['delisted'],
            'effective_from': [pd.Timestamp('2024-06-15')],
            'effective_to': [pd.NaT],
            'index_symbol': [pd.NA],
        }
    )

    before = historical_universe_snapshot(
        universe,
        events,
        pd.Timestamp('2024-05-31'),
    )
    after = historical_universe_snapshot(
        universe,
        events,
        pd.Timestamp('2024-06-30'),
    )

    assert set(before['security_id']) == {'LIVE', 'OLD'}
    assert set(after['security_id']) == {'LIVE'}
    assert before.set_index('security_id').loc['OLD', 'listing_status_basis'] == (
        'dated_delisting_after_decision'
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


def test_bloomberg_database_date_is_the_trusted_availability_boundary():
    statements = pd.DataFrame(
        {
            'security_id': ['A'],
            'fiscal_period_end': ['2021-06-30'],
            'filing_date': ['2021-08-19'],
            'available_from': ['2021-08-31'],
            'source': ['bloomberg_database_as_of'],
        }
    )
    result = reconstruct_statement_availability(statements, 120)
    assert result.loc[0, 'reconstructed_available_from'] == pd.Timestamp('2021-08-31')
    assert result.loc[0, 'availability_basis'] == 'bloomberg_fundamental_database_as_of'


def test_fundamental_snapshot_uses_latest_vintage_available_at_anchor():
    statements = pd.DataFrame(
        {
            'security_id': ['A', 'A'],
            'fiscal_period_end': pd.to_datetime(['2020-12-31', '2020-12-31']),
            'fiscal_period_type': ['annual', 'annual'],
            'reconstructed_available_from': pd.to_datetime(['2021-03-01', '2021-09-01']),
            'retrieved_at': pd.to_datetime(['2026-08-13', '2026-08-13']),
            'revenue_usd': [100.0, 120.0],
            'free_cash_flow_usd': [10.0, 12.0],
            'dps': [1.0, 1.0],
        }
    )
    before_revision = _fundamental_snapshot(statements, pd.Timestamp('2021-08-31'), 1)
    after_revision = _fundamental_snapshot(statements, pd.Timestamp('2021-09-30'), 1)
    assert before_revision.loc[0, 'security_id'] == 'A'
    assert before_revision.loc[0, 'revenue_usd'] == 100.0
    assert after_revision.loc[0, 'revenue_usd'] == 120.0


def test_future_high_priority_vendor_does_not_erase_available_filing():
    statements = pd.DataFrame(
        {
            'security_id': ['A', 'A'],
            'fiscal_period_end': pd.to_datetime(['2020-12-31', '2020-12-31']),
            'fiscal_period_type': ['annual', 'annual'],
            'reconstructed_available_from': pd.to_datetime(
                ['2021-04-30', '2021-08-31']
            ),
            'retrieved_at': pd.to_datetime(['2026-08-13', '2026-08-13']),
            'source': ['eastmoney_china_financials', 'bloomberg_database_as_of'],
            'source_priority': [3, 1],
            'revenue_usd': [100.0, 110.0],
            'free_cash_flow_usd': [10.0, 11.0],
            'dps': [1.0, 1.1],
        }
    )

    july = _fundamental_snapshot(statements, pd.Timestamp('2021-07-31'), 1)
    september = _fundamental_snapshot(statements, pd.Timestamp('2021-09-30'), 1)

    assert july.loc[0, 'revenue_usd'] == 100.0
    assert september.loc[0, 'revenue_usd'] == 110.0


def test_market_cap_matcher_never_uses_future_snapshot():
    snapshots = pd.DataFrame(
        {
            'security_id': ['A', 'A'],
            'as_of_date': pd.to_datetime(['2024-01-31', '2024-02-29']),
            'available_from': pd.to_datetime(['2024-01-31', '2024-02-29']),
            'retrieved_at': pd.to_datetime(['2026-08-13', '2026-08-13']),
            'market_cap_local': [100.0, 200.0],
            'shares_outstanding': [10.0, 20.0],
            'currency': ['USD', 'USD'],
        }
    )
    match = _MarketCapMatcher(snapshots).match(pd.Series(['A']), pd.Timestamp('2024-02-15'))
    assert match.loc[0, 'pit_market_cap_local'] == 100.0
    assert match.loc[0, 'pit_market_cap_as_of_date'] == pd.Timestamp('2024-01-31')


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
