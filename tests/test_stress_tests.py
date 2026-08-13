import pandas as pd

from src.portfolio.portfolio_loader import load_current_portfolio
from src.risk.stress_testing import run_stress_test_contributions, run_stress_tests


def test_stress_testing_outputs_losses():
    portfolio = load_current_portfolio("data/external/current_portfolio_template.csv")
    report = run_stress_tests(portfolio)
    assert "portfolio_loss_pct" in report.columns
    assert len(report) >= 5


def test_cash_has_zero_stress_shock_with_nullable_features():
    portfolio = pd.DataFrame(
        [
            {
                "security_id": "CASH",
                "ticker": "CASH",
                "instrument_type": "Cash",
                "company_name": "USD Cash",
                "sector": "Cash",
                "country": "Cash",
                "region": "Cash",
                "currency": "USD",
                "target_weight": 0.20,
                "balance_sheet_strength_score": pd.NA,
            }
        ]
    )
    contributions = run_stress_test_contributions(portfolio)
    assert contributions["shock_pct"].eq(0.0).all()
    assert contributions["stress_driver"].eq("cash").all()
