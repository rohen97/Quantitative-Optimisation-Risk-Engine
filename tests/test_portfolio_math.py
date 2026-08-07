from __future__ import annotations

import numpy as np
import pandas as pd

from src.optimisation.portfolio_math import calculate_portfolio_volatility


def _brute_force_volatility(portfolio: pd.DataFrame) -> float:
    exposure = (
        portfolio["target_weight"].fillna(0).to_numpy(dtype=float)
        * portfolio["expected_volatility_12m"].fillna(0.20).to_numpy(dtype=float)
    )
    variance = float(np.square(exposure).sum())
    for i in range(len(portfolio)):
        for j in range(i + 1, len(portfolio)):
            left = portfolio.iloc[i]
            right = portfolio.iloc[j]
            if left["sector"] == right["sector"]:
                correlation = 0.60
            elif left["country"] == right["country"]:
                correlation = 0.50
            elif left["region"] == right["region"]:
                correlation = 0.40
            elif left["currency"] == right["currency"]:
                correlation = 0.35
            else:
                correlation = 0.25
            variance += 2 * exposure[i] * exposure[j] * correlation
    return float(np.sqrt(max(variance, 0.0)))


def test_vectorised_portfolio_volatility_matches_pairwise_hierarchy() -> None:
    portfolio = pd.DataFrame(
        {
            "target_weight": [0.20, 0.15, 0.10, 0.18, 0.12, 0.0, 0.25],
            "expected_volatility_12m": [0.14, 0.18, 0.20, 0.16, 0.24, 0.30, 0.12],
            "sector": ["Tech", "Tech", "Banks", "Banks", "Energy", "Health", "Utilities"],
            "country": ["US", "DE", "DE", "FR", "CN", "US", "GB"],
            "region": ["US", "DACH", "DACH", "EU", "China", "US", "UK"],
            "currency": ["USD", "EUR", "EUR", "EUR", "USD", "USD", "GBP"],
        }
    )

    actual = calculate_portfolio_volatility(portfolio)
    expected = _brute_force_volatility(portfolio)

    assert np.isclose(actual, expected, rtol=1e-12, atol=1e-12)
