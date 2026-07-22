from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd


DEFAULT_REWARD_WEIGHTS = {
    "differential_sharpe": 0.30,
    "net_total_return": 0.20,
    "dividend_income": 0.10,
    "regime_suitability_change": 0.08,
    "diversification_improvement": 0.07,
    "quality_improvement": 0.05,
    "cvar_penalty": 0.10,
    "expected_shortfall_penalty": 0.10,
    "drawdown_penalty": 0.10,
    "transaction_cost_penalty": 0.07,
    "turnover_penalty": 0.05,
    "concentration_penalty": 0.05,
    "dividend_cut_risk_penalty": 0.04,
    "liquidity_penalty": 0.04,
    "forecast_uncertainty_penalty": 0.03,
    "narrative_credit_penalty": 0.03,
    "stress_loss_penalty": 0.02,
    "soft_constraint_breach_penalty": 0.05,
}


@dataclass
class DifferentialSharpeState:
    first_moment: float = 0.0
    second_moment: float = 0.0


@dataclass(frozen=True)
class RewardBreakdown:
    total_reward: float
    differential_sharpe: float
    net_return_component: float
    dividend_component: float
    regime_component: float
    diversification_component: float
    quality_component: float
    cvar_penalty: float
    drawdown_penalty: float
    transaction_cost_penalty: float
    turnover_penalty: float
    dividend_risk_penalty: float
    liquidity_penalty: float
    narrative_credit_penalty: float
    stress_penalty: float
    expected_shortfall_penalty: float = 0.0
    concentration_penalty: float = 0.0
    forecast_uncertainty_penalty: float = 0.0
    soft_constraint_breach_penalty: float = 0.0


def reward_weights(config: dict | None = None) -> dict[str, float]:
    """Load configurable reward weights with conservative defaults."""
    cfg = (config or {}).get("reward", config or {})
    weights = DEFAULT_REWARD_WEIGHTS.copy()
    weights.update({key: float(value) for key, value in cfg.get("weights", {}).items()})
    return weights


def differential_sharpe_ratio(returns: np.ndarray, eps: float = 1e-8) -> float:
    """Return a stable Sharpe proxy suitable for mock PPO rewards."""
    values = np.asarray(returns, dtype=float)
    if values.size == 0:
        return 0.0
    return float(values.mean() / (values.std(ddof=0) + eps))


def differential_sharpe_reward(
    portfolio_return: float,
    state: DifferentialSharpeState,
    eta: float = 1.0 / 252.0,
    epsilon: float = 1e-12,
) -> tuple[float, DifferentialSharpeState]:
    """Online Differential Sharpe Ratio using exponentially updated moments."""
    a_prev = float(state.first_moment)
    b_prev = float(state.second_moment)
    delta_a = float(portfolio_return) - a_prev
    delta_b = float(portfolio_return) ** 2 - b_prev
    denominator = max(b_prev - a_prev**2, epsilon) ** 1.5
    dsr = (b_prev * delta_a - 0.5 * a_prev * delta_b) / denominator
    new_state = DifferentialSharpeState(
        first_moment=a_prev + eta * delta_a,
        second_moment=b_prev + eta * delta_b,
    )
    if not math.isfinite(dsr):
        dsr = 0.0
    return float(dsr), new_state


def _positive(value: float) -> float:
    return max(float(value), 0.0)


def _loss(value: float) -> float:
    return abs(min(float(value), 0.0))


def calculate_reward_breakdown(
    net_total_return: float,
    differential_sharpe: float,
    dividend_income: float,
    regime_suitability_change: float = 0.0,
    diversification_improvement: float = 0.0,
    quality_improvement: float = 0.0,
    cash_flow_quality_exposure: float = 0.0,
    dividend_safety_exposure: float = 0.0,
    cvar: float = 0.0,
    expected_shortfall: float = 0.0,
    drawdown_increment: float = 0.0,
    transaction_costs: float = 0.0,
    turnover: float = 0.0,
    concentration: float = 0.0,
    dividend_cut_risk: float = 0.0,
    liquidity_risk: float = 0.0,
    forecast_uncertainty: float = 0.0,
    narrative_risk: float = 0.0,
    credit_stress_risk: float = 0.0,
    stress_scenario_loss: float = 0.0,
    soft_constraint_breaches: float = 0.0,
    config: dict | None = None,
) -> RewardBreakdown:
    """Calculate a decomposed conservative DRL reward.

    Hard constraints are expected to be handled by masking/projection before
    this function is called; this reward only prices soft trade-offs.
    """
    weights = reward_weights(config)
    net_component = weights["net_total_return"] * float(net_total_return)
    dsr_component = weights["differential_sharpe"] * float(differential_sharpe)
    dividend_component = weights["dividend_income"] * float(dividend_income)
    regime_component = weights["regime_suitability_change"] * float(regime_suitability_change)
    diversification_component = weights["diversification_improvement"] * float(diversification_improvement)
    combined_quality = float(quality_improvement) + 0.5 * float(cash_flow_quality_exposure) + 0.5 * float(dividend_safety_exposure)
    quality_component = weights["quality_improvement"] * combined_quality
    cvar_penalty = weights["cvar_penalty"] * _loss(cvar)
    es_penalty = weights["expected_shortfall_penalty"] * _loss(expected_shortfall)
    drawdown_penalty = weights["drawdown_penalty"] * _positive(drawdown_increment)
    transaction_penalty = weights["transaction_cost_penalty"] * _positive(transaction_costs)
    turnover_penalty = weights["turnover_penalty"] * _positive(turnover)
    concentration_penalty = weights["concentration_penalty"] * _positive(concentration)
    dividend_risk_penalty = weights["dividend_cut_risk_penalty"] * _positive(dividend_cut_risk)
    liquidity_penalty = weights["liquidity_penalty"] * _positive(liquidity_risk)
    uncertainty_penalty = weights["forecast_uncertainty_penalty"] * _positive(forecast_uncertainty)
    narrative_credit_penalty = weights["narrative_credit_penalty"] * _positive(narrative_risk + credit_stress_risk)
    stress_penalty = weights["stress_loss_penalty"] * _loss(stress_scenario_loss)
    soft_breach_penalty = weights["soft_constraint_breach_penalty"] * _positive(soft_constraint_breaches)
    total = (
        dsr_component
        + net_component
        + dividend_component
        + regime_component
        + diversification_component
        + quality_component
        - cvar_penalty
        - es_penalty
        - drawdown_penalty
        - transaction_penalty
        - turnover_penalty
        - concentration_penalty
        - dividend_risk_penalty
        - liquidity_penalty
        - uncertainty_penalty
        - narrative_credit_penalty
        - stress_penalty
        - soft_breach_penalty
    )
    return RewardBreakdown(
        total_reward=float(total),
        differential_sharpe=float(dsr_component),
        net_return_component=float(net_component),
        dividend_component=float(dividend_component),
        regime_component=float(regime_component),
        diversification_component=float(diversification_component),
        quality_component=float(quality_component),
        cvar_penalty=float(cvar_penalty),
        expected_shortfall_penalty=float(es_penalty),
        drawdown_penalty=float(drawdown_penalty),
        transaction_cost_penalty=float(transaction_penalty),
        turnover_penalty=float(turnover_penalty),
        concentration_penalty=float(concentration_penalty),
        dividend_risk_penalty=float(dividend_risk_penalty),
        liquidity_penalty=float(liquidity_penalty),
        forecast_uncertainty_penalty=float(uncertainty_penalty),
        narrative_credit_penalty=float(narrative_credit_penalty),
        stress_penalty=float(stress_penalty),
        soft_constraint_breach_penalty=float(soft_breach_penalty),
    )


def reward_decomposition(
    portfolio_return: float,
    dividend_income: float,
    volatility: float,
    cvar: float,
    drawdown: float,
    turnover: float,
    transaction_cost: float,
    slippage: float,
    liquidity_penalty: float,
    config: dict | None = None,
) -> dict[str, float]:
    """Compatibility wrapper returning the richer reward decomposition as a dict."""
    dsr, _ = differential_sharpe_reward(float(portfolio_return), DifferentialSharpeState())
    breakdown = calculate_reward_breakdown(
        net_total_return=float(portfolio_return) - float(transaction_cost) - float(slippage),
        differential_sharpe=dsr,
        dividend_income=dividend_income,
        cvar=cvar,
        expected_shortfall=cvar,
        drawdown_increment=abs(min(float(drawdown), 0.0)),
        transaction_costs=float(transaction_cost) + float(slippage),
        turnover=turnover,
        liquidity_risk=liquidity_penalty,
        config=config,
    )
    output = breakdown.__dict__.copy()
    output.update(
        {
            "gross_return_component": float(portfolio_return) + float(dividend_income),
            "dividend_income_component": float(dividend_income),
            "risk_penalty": output["cvar_penalty"] + output["expected_shortfall_penalty"],
            "transaction_cost": float(transaction_cost),
            "slippage": float(slippage),
            "net_reward": output["total_reward"],
        }
    )
    return output


def build_reward_report(rows: list[dict[str, float]]) -> pd.DataFrame:
    """Convert reward decomposition rows to a report frame."""
    return pd.DataFrame(rows)
