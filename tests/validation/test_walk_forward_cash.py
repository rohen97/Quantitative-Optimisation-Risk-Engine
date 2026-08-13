import pandas as pd
import pytest

from src.validation.walk_forward import (
    CASH_SECURITY_ID,
    _apply_walk_forward_rebalance_control,
    _cardinality_constrained_portfolio,
    _constraint_rows,
)


def test_reconstructed_fallback_uses_cash_without_relaxing_equity_caps():
    rows = []
    for index in range(15):
        group = index // 5
        rows.append(
            {
                'security_id': f'SEC-{index:02d}',
                'ticker': f'SEC-{index:02d}',
                'issuer_id': f'ISSUER-{index:02d}',
                'company_name': f'Company {index:02d}',
                'instrument_type': 'Equity',
                'listing_status': 'Active',
                'exchange_code': 'TEST',
                'country': f'Country {group}',
                'region': f'Region {group}',
                'sector': f'Sector {index % 3}',
                'industry': 'Industry',
                'currency': f'CCY{group}',
                'market_cap_usd': 1_000_000_000,
                'average_daily_value_usd': 10_000_000,
                'volatility_1y': 0.20,
                'passes_hard_filters': True,
                'final_recommendation_score': 100 - index,
            }
        )
    scorecard = pd.DataFrame(rows)
    constraints = {
        'max_single_name_weight': 0.05,
        'max_sector_weight': 0.25,
        'max_country_weight': 0.30,
        'max_region_weight': 0.40,
        'max_currency_weight': 0.40,
        'minimum_effective_number_of_holdings': 15,
        'maximum_cash_weight': 0.25,
    }

    portfolio = _cardinality_constrained_portfolio(scorecard, constraints)

    assert portfolio['target_weight'].sum() == 1.0
    assert portfolio.loc[
        portfolio['security_id'].eq(CASH_SECURITY_ID), 'target_weight'
    ].iloc[0] == 0.25
    portfolio['weight'] = portfolio['target_weight']
    report = _constraint_rows(portfolio, pd.Timestamp('2021-07-31'))
    assert not report['breach_flag'].any()


def test_cardinality_constraint_preserves_exact_weight_cap_slots():
    rows = []
    countries = ['China'] * 6 + ['United States'] * 6 + ['Hong Kong'] * 4
    for index, country in enumerate(countries):
        rows.append(
            {
                'security_id': f'SEC-{index:02d}',
                'ticker': f'SEC-{index:02d}',
                'issuer_id': f'ISSUER-{index:02d}',
                'company_name': f'Company {index:02d}',
                'instrument_type': 'Equity',
                'listing_status': 'Active',
                'exchange_code': 'TEST',
                'country': country,
                'region': country,
                'sector': f'Sector {index % 4}',
                'industry': 'Industry',
                'currency': country,
                'market_cap_usd': 1_000_000_000,
                'average_daily_value_usd': 10_000_000,
                'volatility_1y': 0.20,
                'passes_hard_filters': True,
                'final_recommendation_score': 100 - index,
            }
        )
    constraints = {
        'max_single_name_weight': 0.05,
        'max_sector_weight': 0.25,
        'max_country_weight': 0.30,
        'max_region_weight': 0.40,
        'max_currency_weight': 0.40,
        'minimum_effective_number_of_holdings': 15,
        'maximum_cash_weight': 0.25,
    }

    portfolio = _cardinality_constrained_portfolio(pd.DataFrame(rows), constraints)
    equities = portfolio.loc[~portfolio['security_id'].eq(CASH_SECURITY_ID)]

    assert len(equities) == 16
    assert equities.groupby('country')['target_weight'].sum()['China'] == pytest.approx(
        0.30
    )
    assert portfolio.loc[
        portfolio['security_id'].eq(CASH_SECURITY_ID), 'target_weight'
    ].sum() == pytest.approx(0.20)


def test_post_fallback_rebalance_control_caps_turnover():
    rows = []
    for index in range(40):
        rows.append(
            {
                'security_id': f'SEC-{index:02d}',
                'ticker': f'SEC-{index:02d}',
                'issuer_id': f'ISSUER-{index:02d}',
                'company_name': f'Company {index:02d}',
                'instrument_type': 'Equity',
                'listing_status': 'Active',
                'final_recommendation': 'Buy',
                'country': f'Country {index % 4}',
                'region': f'Region {index % 4}',
                'sector': f'Sector {index % 5}',
                'industry': 'Industry',
                'currency': f'CCY{index % 4}',
                'liquidity_score': 80,
                'average_daily_value_usd': 10_000_000,
                'dividend_cut_probability': 0.10,
                'large_drawdown_probability_12m': 0.10,
                'forecast_uncertainty_score': 30,
                'tail_risk_score': 30,
                'regime_exclusion_flag': False,
                'reframing_exclusion_flag': False,
                'alt_data_exclusion_flag': False,
                'price_data_exclusion_flag': False,
                'passes_hard_filters': True,
            }
        )
    scorecard = pd.DataFrame(rows)
    target = scorecard.iloc[:20].copy()
    target['target_weight'] = 0.05
    previous = pd.Series(
        0.05,
        index=scorecard.iloc[20:]['security_id'],
        dtype=float,
    )
    controlled = _apply_walk_forward_rebalance_control(
        target,
        previous,
        scorecard,
        {
            'max_single_name_weight': 0.05,
            'max_sector_weight': 1.0,
            'max_country_weight': 1.0,
            'max_region_weight': 1.0,
            'max_currency_weight': 1.0,
            'maximum_cash_weight': 0.25,
            'maximum_turnover': 0.10,
            'minimum_rebalance_turnover': 0.01,
        },
    )
    assert controlled['target_weight'].sum() == pytest.approx(1.0)
    assert controlled['projected_turnover'].iloc[0] == pytest.approx(0.10)
    assert controlled['turnover_constraint_applied'].all()


def test_post_fallback_control_accepts_scorecard_recommendation_column():
    scorecard = pd.DataFrame(
        [
            {
                'security_id': f'SEC-{index:02d}',
                'ticker': f'SEC-{index:02d}',
                'issuer_id': f'ISSUER-{index:02d}',
                'company_name': f'Company {index:02d}',
                'instrument_type': 'Equity',
                'listing_status': 'Active',
                'recommendation': 'Buy / Accumulate',
                'country': 'Country',
                'region': 'Region',
                'sector': f'Sector {index % 5}',
                'currency': 'USD',
                'liquidity_score': 80,
                'average_daily_value_usd': 10_000_000,
                'dividend_cut_probability': 0.10,
                'large_drawdown_probability_12m': 0.10,
                'forecast_uncertainty_score': 30,
                'tail_risk_score': 30,
                'passes_hard_filters': True,
            }
            for index in range(20)
        ]
    )
    target = scorecard.copy()
    target['target_weight'] = 0.05
    previous = pd.Series(0.05, index=scorecard['security_id'], dtype=float)
    controlled = _apply_walk_forward_rebalance_control(
        target,
        previous,
        scorecard,
        {
            'max_single_name_weight': 0.05,
            'maximum_cash_weight': 0.25,
            'maximum_turnover': 0.10,
            'minimum_rebalance_turnover': 0.01,
        },
    )
    assert controlled['projected_turnover'].iloc[0] == pytest.approx(0.0)
    assert controlled['forced_exit_turnover'].iloc[0] == pytest.approx(0.0)


def test_hard_exit_reallocation_remains_feasible_and_minimum_turnover():
    rows = []
    for index in range(40):
        rows.append(
            {
                'security_id': f'SEC-{index:02d}',
                'ticker': f'SEC-{index:02d}',
                'issuer_id': f'ISSUER-{index:02d}',
                'company_name': f'Company {index:02d}',
                'instrument_type': 'Equity',
                'listing_status': 'Active',
                'recommendation': 'Buy / Accumulate',
                'country': 'Country',
                'region': 'Region',
                'sector': f'Sector {index % 5}',
                'currency': 'USD',
                'liquidity_score': 80,
                'average_daily_value_usd': 10_000_000,
                'dividend_cut_probability': 0.10,
                'large_drawdown_probability_12m': 0.10,
                'forecast_uncertainty_score': 30,
                'tail_risk_score': 30,
                'price_data_exclusion_flag': index in {20, 21},
                'passes_hard_filters': index not in {20, 21},
            }
        )
    scorecard = pd.DataFrame(rows)
    target = scorecard.iloc[:20].copy()
    target['target_weight'] = 0.05
    previous = pd.Series(
        0.05,
        index=scorecard.iloc[20:]['security_id'],
        dtype=float,
    )
    controlled = _apply_walk_forward_rebalance_control(
        target,
        previous,
        scorecard,
        {
            'max_single_name_weight': 0.05,
            'maximum_cash_weight': 0.25,
            'maximum_turnover': 0.10,
            'minimum_rebalance_turnover': 0.01,
        },
    )
    assert controlled['forced_exit_weight'].iloc[0] == pytest.approx(0.10)
    assert controlled['forced_exit_turnover'].iloc[0] == pytest.approx(0.10)
    assert controlled['projected_turnover'].iloc[0] == pytest.approx(0.10)
    assert not controlled['turnover_control_feasibility_override'].any()
    assert controlled['target_weight'].max() <= 0.05 + 1.0e-10
    assert not controlled['security_id'].isin(['SEC-20', 'SEC-21']).any()
