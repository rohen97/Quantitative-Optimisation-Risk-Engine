from src.portfolio.portfolio_loader import load_current_portfolio
from src.risk.stress_testing import run_stress_tests


def test_stress_testing_outputs_losses():
    portfolio = load_current_portfolio("data/external/current_portfolio_template.csv")
    report = run_stress_tests(portfolio)
    assert "portfolio_loss_pct" in report.columns
    assert len(report) >= 5
