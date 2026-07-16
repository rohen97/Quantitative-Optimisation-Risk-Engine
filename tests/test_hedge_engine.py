import pandas as pd

from src.hedging.defensive_substitutions import build_defensive_substitution_recommendations
from src.hedging.hedge_report import build_hedge_outputs


def test_hedge_recommendations_and_substitutions_are_created():
    portfolio = pd.DataFrame(
        {
            "security_id": ["S1", "S2"],
            "ticker": ["RISK", "SAFE"],
            "company_name": ["Risk", "Safe"],
            "target_weight": [0.05, 0.05],
            "sector": ["Industrials", "Industrials"],
            "country": ["Germany", "Germany"],
            "region": ["DACH", "DACH"],
            "currency": ["EUR", "EUR"],
            "dividend_safety_score": [30, 80],
            "dividend_cut_probability": [0.50, 0.05],
            "large_drawdown_probability_12m": [0.50, 0.10],
            "cvar_5_12m": [-0.40, -0.10],
            "tail_risk_score": [90, 10],
            "dividend_yield": [0.06, 0.04],
            "expected_total_return_12m": [0.08, 0.06],
            "regime_suitability_score": [30, 80],
            "liquidity_score": [30, 90],
        }
    )
    stress = pd.DataFrame([{"scenario_name": "global_risk_off", "portfolio_loss_pct": -0.2, "hedge_required_flag": True}])
    hedges, substitutions = build_hedge_outputs(portfolio, None, stress, portfolio)
    assert not hedges.empty
    assert not substitutions.empty
    assert "hedge_category" in hedges.columns
