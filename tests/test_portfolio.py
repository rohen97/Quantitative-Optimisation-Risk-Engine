import pytest

from src.data_ingestion.mock_data import generate_mock_current_portfolio, generate_mock_universe
from src.portfolio.concentration import effective_number_of_holdings, hhi
from src.portfolio.exposure import exposure_by
from src.portfolio.portfolio_loader import load_current_portfolio


def test_portfolio_loading_and_concentration():
    portfolio = load_current_portfolio(mock_portfolio=generate_mock_current_portfolio(generate_mock_universe()))
    assert pytest.approx(portfolio["weight"].sum()) == 1
    assert hhi(portfolio["weight"]) > 0
    assert effective_number_of_holdings(portfolio["weight"]) > 1


def test_exposure_calculations_sum_to_one():
    portfolio = load_current_portfolio(mock_portfolio=generate_mock_current_portfolio(generate_mock_universe()))
    exposure = exposure_by(portfolio, "sector")
    assert pytest.approx(exposure["weight"].sum()) == 1
