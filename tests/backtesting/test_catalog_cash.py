from __future__ import annotations

import pandas as pd

from src.backtesting.portfolio_catalog import _build_holdings


def test_explicit_cash_is_left_for_the_backtest_cash_sleeve() -> None:
    weights = pd.DataFrame(
        {"ticker": ["AAA.US", "CASH"], "weight": [0.75, 0.25]}
    )
    metadata = pd.DataFrame(
        {
            "ticker": ["AAA.US", "CASH"],
            "security_id": ["AAA.US", "CASH"],
            "company_name": ["AAA", "Cash"],
        }
    )

    result = _build_holdings(weights, metadata, {})

    assert result["ticker"].tolist() == ["AAA.US"]
    assert result["weight"].sum() == 0.75
