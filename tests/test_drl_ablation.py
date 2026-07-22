import pandas as pd

from src.drl.ablation import build_ablation_results


def test_drl_ablation_results_are_reportable():
    ablation = build_ablation_results(pd.DataFrame({"net_risk_adjusted_return_delta": [0.01]}))
    expected_ablations = {
        "without_regime_features",
        "with_regime_features",
        "without_distributional_features",
        "with_distributional_features",
        "without_sentiment_narrative",
        "with_sentiment_narrative",
        "differential_sharpe_reward_only",
        "full_conservative_reward",
        "no_transaction_costs",
        "realistic_transaction_costs",
        "universal_agent",
        "regime_specialist_blend",
        "mlp_encoder",
        "tcn_gap_encoder_when_available",
        "no_risk_throttle",
        "wolf_chaos_risk_throttle",
    }
    assert set(ablation["ablation"]) == expected_ablations
    assert {
        "net_return",
        "sharpe",
        "cvar",
        "drawdown",
        "turnover",
        "dividend_yield",
        "worst_scenario_loss",
        "seed_dispersion",
        "feature_value_added",
    }.issubset(ablation.columns)
