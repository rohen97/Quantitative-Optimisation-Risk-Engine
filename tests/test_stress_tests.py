from src.data_ingestion.mock_data import generate_mock_current_portfolio, generate_mock_universe
from src.portfolio.portfolio_loader import load_current_portfolio
from src.risk.stress_testing import run_stress_tests


def test_stress_testing_outputs_losses():
    portfolio = load_current_portfolio(mock_portfolio=generate_mock_current_portfolio(generate_mock_universe()))
    report = run_stress_tests(portfolio)
    assert "portfolio_loss_pct" in report.columns
    assert len(report) >= 5
