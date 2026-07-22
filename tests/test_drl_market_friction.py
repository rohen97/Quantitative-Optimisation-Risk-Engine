import numpy as np
import pandas as pd

from src.drl.market_friction import calculate_market_friction_costs


def test_market_friction_formulas_are_weight_based_costs():
    metadata = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB"],
            "average_daily_value_usd": [10_000_000, 5_000_000],
            "currency": ["EUR", "USD"],
            "country": ["DE", "GB"],
        }
    )
    result = calculate_market_friction_costs(
        np.array([0.55, 0.45]),
        np.array([0.50, 0.50]),
        metadata,
        1_000_000,
        {
            "market_friction": {
                "commission_bps": 10,
                "half_spread_bps": 4,
                "impact_coefficient": 8,
                "currency_conversion_bps": 2,
                "enable_country_transaction_tax": False,
            }
        },
    )
    assert round(result.turnover, 10) == 0.10
    assert round(result.traded_notional, 6) == 100_000
    assert round(result.commission_cost, 10) == 0.0001
    assert round(result.half_spread_cost, 10) == 0.00004
    assert result.nonlinear_market_impact > 0
    assert round(result.currency_conversion_cost, 10) == 0.00001
    assert result.transaction_tax_cost == 0
    assert result.total_cost > result.commission_cost + result.half_spread_cost


def test_market_friction_uses_conservative_missing_adv_and_optional_tax():
    metadata = pd.DataFrame({"ticker": ["AAA"], "currency": ["GBP"], "country": ["UK"]})
    result = calculate_market_friction_costs(
        np.array([0.60]),
        np.array([0.50]),
        metadata,
        2_000_000,
        {
            "market_friction": {
                "commission_bps": 0,
                "half_spread_bps": 0,
                "impact_coefficient": 10,
                "missing_adv_usd": 1_000_000,
                "minimum_adv_usd": 1_000_000,
                "enable_country_transaction_tax": True,
                "country_transaction_tax_bps": {"UK": 50},
            }
        },
    )
    assert round(result.max_participation_rate, 10) == 0.2
    assert round(result.transaction_tax_cost, 10) == 0.0005
    assert result.total_cost > result.transaction_tax_cost
