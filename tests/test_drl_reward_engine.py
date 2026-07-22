import numpy as np

from src.drl.reward_engine import (
    DifferentialSharpeState,
    RewardBreakdown,
    calculate_reward_breakdown,
    differential_sharpe_ratio,
    differential_sharpe_reward,
    reward_decomposition,
)


def test_drl_reward_penalises_costs_and_risk():
    base = reward_decomposition(0.08, 0.03, 0.12, -0.15, -0.08, 0.05, 0.001, 0.001, 0.001)
    worse = reward_decomposition(0.08, 0.03, 0.25, -0.30, -0.20, 0.20, 0.005, 0.005, 0.005)
    assert base["net_reward"] > worse["net_reward"]
    assert differential_sharpe_ratio(np.array([0.01, 0.02, -0.01])) != 0


def test_differential_sharpe_reward_updates_online_state():
    dsr, state = differential_sharpe_reward(0.01, DifferentialSharpeState(first_moment=0.001, second_moment=0.0002))
    assert isinstance(dsr, float)
    assert state.first_moment != 0.001
    assert state.second_moment != 0.0002


def test_reward_breakdown_is_decomposed_and_configurable():
    reward = calculate_reward_breakdown(
        net_total_return=0.05,
        differential_sharpe=0.20,
        dividend_income=0.03,
        regime_suitability_change=0.02,
        diversification_improvement=0.01,
        quality_improvement=0.03,
        cash_flow_quality_exposure=0.02,
        dividend_safety_exposure=0.04,
        cvar=-0.12,
        expected_shortfall=-0.14,
        drawdown_increment=0.05,
        transaction_costs=0.002,
        turnover=0.10,
        concentration=0.08,
        dividend_cut_risk=0.10,
        liquidity_risk=0.05,
        forecast_uncertainty=0.20,
        narrative_risk=0.10,
        credit_stress_risk=0.05,
        stress_scenario_loss=-0.08,
        soft_constraint_breaches=1,
        config={"reward": {"weights": {"net_total_return": 0.50, "soft_constraint_breach_penalty": 0.01}}},
    )
    assert isinstance(reward, RewardBreakdown)
    assert reward.net_return_component == 0.025
    assert round(reward.quality_component, 10) == 0.003
    assert reward.soft_constraint_breach_penalty == 0.01
    assert reward.total_reward < reward.differential_sharpe + reward.net_return_component + reward.dividend_component


def test_reward_directional_effects_and_decomposition_sum():
    base = calculate_reward_breakdown(
        net_total_return=0.04,
        differential_sharpe=0.10,
        dividend_income=0.02,
        cvar=-0.10,
        expected_shortfall=-0.10,
        drawdown_increment=0.02,
        transaction_costs=0.001,
        turnover=0.02,
    )
    higher_cost = calculate_reward_breakdown(
        net_total_return=0.04,
        differential_sharpe=0.10,
        dividend_income=0.02,
        cvar=-0.10,
        expected_shortfall=-0.10,
        drawdown_increment=0.02,
        transaction_costs=0.02,
        turnover=0.02,
    )
    worse_cvar = calculate_reward_breakdown(
        net_total_return=0.04,
        differential_sharpe=0.10,
        dividend_income=0.02,
        cvar=-0.30,
        expected_shortfall=-0.10,
        drawdown_increment=0.02,
        transaction_costs=0.001,
        turnover=0.02,
    )
    worse_drawdown = calculate_reward_breakdown(
        net_total_return=0.04,
        differential_sharpe=0.10,
        dividend_income=0.02,
        cvar=-0.10,
        expected_shortfall=-0.10,
        drawdown_increment=0.20,
        transaction_costs=0.001,
        turnover=0.02,
    )
    higher_dividend = calculate_reward_breakdown(
        net_total_return=0.04,
        differential_sharpe=0.10,
        dividend_income=0.08,
        cvar=-0.10,
        expected_shortfall=-0.10,
        drawdown_increment=0.02,
        transaction_costs=0.001,
        turnover=0.02,
    )

    assert np.isfinite(base.total_reward)
    assert higher_cost.total_reward < base.total_reward
    assert worse_cvar.total_reward < base.total_reward
    assert worse_drawdown.total_reward < base.total_reward
    assert higher_dividend.total_reward > base.total_reward
    positives = (
        base.differential_sharpe
        + base.net_return_component
        + base.dividend_component
        + base.regime_component
        + base.diversification_component
        + base.quality_component
    )
    penalties = (
        base.cvar_penalty
        + base.expected_shortfall_penalty
        + base.drawdown_penalty
        + base.transaction_cost_penalty
        + base.turnover_penalty
        + base.concentration_penalty
        + base.dividend_risk_penalty
        + base.liquidity_penalty
        + base.forecast_uncertainty_penalty
        + base.narrative_credit_penalty
        + base.stress_penalty
        + base.soft_constraint_breach_penalty
    )
    assert abs(base.total_reward - (positives - penalties)) < 1e-12
