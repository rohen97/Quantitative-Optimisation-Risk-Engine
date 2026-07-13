from pathlib import Path

import pandas as pd
import pytest

from src.portfolio.concentration import effective_number_of_holdings, hhi
from src.portfolio.exposure import exposure_by
from src.portfolio.portfolio_diagnostics import build_portfolio_diagnostics
from src.portfolio.portfolio_loader import REQUIRED_HOLDING_COLUMNS, enrich_current_portfolio, load_current_portfolio


def sample_portfolio_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "company_name": "Alpha AG",
                "country": "Germany",
                "region": "DACH",
                "currency": "EUR",
                "sector": "Healthcare",
                "shares": 10,
                "current_price": 100,
                "market_value_usd": 1000,
                "dividend_yield": 0.04,
                "beta": 0.8,
                "volatility": 0.20,
            },
            {
                "ticker": "BBB",
                "company_name": "Beta Ltd",
                "country": "India",
                "region": "India",
                "currency": "INR",
                "sector": "Financials",
                "shares": 20,
                "current_price": 50,
                "market_value_usd": 1000,
                "dividend_yield": 0.02,
                "beta": 1.2,
                "volatility": 0.30,
            },
        ]
    )


def test_portfolio_loading_from_csv(tmp_path: Path):
    path = tmp_path / "portfolio.csv"
    sample_portfolio_frame().to_csv(path, index=False)
    portfolio = load_current_portfolio(path)
    assert set(REQUIRED_HOLDING_COLUMNS).issubset(portfolio.columns)
    assert pytest.approx(portfolio["weight"].sum()) == 1
    assert "dividend_income_usd" in portfolio.columns


def test_missing_required_columns_raise_error():
    frame = sample_portfolio_frame().drop(columns=["volatility"])
    with pytest.raises(ValueError, match="missing required columns"):
        enrich_current_portfolio(frame)


def test_hhi_and_effective_number_of_holdings():
    weights = pd.Series([0.5, 0.5])
    assert hhi(weights) == pytest.approx(0.5)
    assert effective_number_of_holdings(weights) == pytest.approx(2.0)


def test_exposure_calculations_sum_to_one():
    portfolio = enrich_current_portfolio(sample_portfolio_frame())
    exposure = exposure_by(portfolio, "sector")
    assert pytest.approx(exposure["weight"].sum()) == 1
    assert set(exposure["sector"]) == {"Healthcare", "Financials"}


def test_dividend_income_and_weighted_diagnostics():
    portfolio = enrich_current_portfolio(sample_portfolio_frame())
    diagnostics, exposures = build_portfolio_diagnostics(portfolio)
    assert diagnostics.loc[0, "dividend_income_usd"] == pytest.approx(60)
    assert diagnostics.loc[0, "weighted_dividend_yield"] == pytest.approx(0.03)
    assert diagnostics.loc[0, "weighted_beta"] == pytest.approx(1.0)
    assert diagnostics.loc[0, "weighted_volatility_proxy"] == pytest.approx(0.25)
    assert "region" in exposures
