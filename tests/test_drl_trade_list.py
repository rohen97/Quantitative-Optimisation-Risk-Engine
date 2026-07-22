import numpy as np
import pandas as pd

from src.drl.benchmark import DRLAcceptanceDecision
from src.drl.trade_list import DRL_TRADE_LIST_COLUMNS, build_drl_trade_list


def test_drl_trade_list_has_required_schema_and_baseline_fallback_action():
    asset_data = pd.DataFrame(
        {
            "security_id": ["A", "B"],
            "ticker": ["AAA", "BBB"],
            "company_name": ["Alpha", "Beta"],
            "current_weight": [0.10, 0.00],
            "expected_total_return_12m": [0.08, 0.02],
            "dividend_safety_score": [80, 40],
            "regime_suitability_score": [75, 35],
            "cvar_5_12m": [-0.18, -0.35],
            "large_drawdown_probability_12m": [0.20, 0.45],
            "dividend_cut_probability": [0.10, 0.40],
            "average_daily_value_usd": [10_000_000, 2_000_000],
        }
    )
    projection_report = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB", "CASH"],
            "baseline_weight": [0.10, 0.00, 0.0],
            "candidate_weight": [0.12, 0.03, 0.02],
            "projected_weight": [0.11, 0.00, 0.02],
            "eligible_for_drl": [True, False, True],
        }
    )
    decision = DRLAcceptanceDecision(False, "baseline_optimiser", ("turnover_exceeds_hard_limit",), 0.0, 1.0)

    trades = build_drl_trade_list(asset_data, projection_report, np.array([0.10, 0.00]), decision, 1_000_000)

    assert trades.columns.tolist() == DRL_TRADE_LIST_COLUMNS
    assert set(trades["trade_action"]).issubset({"Buy", "Increase", "Reduce", "Hold", "Exit", "Avoid", "Baseline Fallback"})
    assert "Baseline Fallback" in set(trades["trade_action"])
    assert trades["acceptance_status"].eq("Rejected - Baseline Fallback").all()
    assert trades["transaction_cost_estimate"].ge(0).all()
    assert trades["slippage_estimate"].ge(0).all()
    assert trades["liquidity_impact"].ge(0).all()
