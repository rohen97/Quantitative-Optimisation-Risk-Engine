import pandas as pd

from src.reporting.models import ICDataBundle
from src.reporting.portfolio_resolver import (
    classify_trade_action,
    resolve_final_portfolio,
    resolve_final_portfolio_from_bundle,
)


def test_portfolio_resolver_uses_final_selected_weight():
    bundle = ICDataBundle({"final_recommendations": pd.DataFrame({"ticker": ["AAA"], "final_selected_weight": [0.2], "final_recommendation": ["Buy"]})})
    result = resolve_final_portfolio_from_bundle(bundle)
    assert result.source_name == "equal_weight_fallback"
    assert result.portfolio.loc[0, "final_weight"] == 1.0


def test_portfolio_resolver_uses_precedence_and_ignores_rejected_drl():
    accepted_drl = pd.DataFrame({"ticker": ["AAA", "BBB"], "target_weight": [0.6, 0.4]})
    cvar = pd.DataFrame({"ticker": ["AAA", "BBB"], "target_weight": [0.5, 0.5]})
    rejected = resolve_final_portfolio(
        explicit_final=pd.DataFrame(),
        drl_weights=accepted_drl,
        drl_status="rejected",
        selected_optimiser=pd.DataFrame(),
        cvar_portfolio=cvar,
        regime_portfolio=pd.DataFrame(),
        score_portfolio=pd.DataFrame(),
        equal_weight_portfolio=pd.DataFrame(),
    )
    assert rejected.source_name == "cvar_constrained"
    accepted = resolve_final_portfolio(
        explicit_final=pd.DataFrame(),
        drl_weights=accepted_drl,
        drl_status="blended",
        selected_optimiser=pd.DataFrame(),
        cvar_portfolio=cvar,
        regime_portfolio=pd.DataFrame(),
        score_portfolio=pd.DataFrame(),
        equal_weight_portfolio=pd.DataFrame(),
    )
    assert accepted.source_name == "accepted_drl_blend"


def test_trade_action_classification_rules():
    assert classify_trade_action(0.0, 0.01, False) == "Buy"
    assert classify_trade_action(0.02, 0.03, False) == "Increase"
    assert classify_trade_action(0.03, 0.02, False) == "Reduce"
    assert classify_trade_action(0.03, 0.0, True) == "Exit"
    assert classify_trade_action(0.0, 0.0, True) == "Avoid"
