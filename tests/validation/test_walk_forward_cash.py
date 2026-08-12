import pandas as pd
import pytest

from src.validation.walk_forward import (
    CASH_SECURITY_ID,
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
