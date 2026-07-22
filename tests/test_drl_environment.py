import numpy as np
import pandas as pd

from src.drl.market_environment import DRLMarketEnvironment, WolfPortfolioEnv


def test_drl_environment_projects_and_rewards():
    data = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB"],
            "sector": ["A", "B"],
            "country": ["DE", "GB"],
            "region": ["DACH", "UK"],
            "currency": ["EUR", "GBP"],
            "expected_total_return_12m": [0.08, 0.03],
            "expected_dividend_return_12m": [0.03, 0.04],
            "expected_volatility_12m": [0.18, 0.22],
            "cvar_5_12m": [-0.18, -0.25],
            "large_drawdown_probability_12m": [0.15, 0.25],
            "liquidity_score": [70, 50],
        }
    )
    env = DRLMarketEnvironment(data, np.array([0.5, 0.5]), np.array([True, True]), {"max_single_name_weight": 0.7}, {})
    result = env.step(np.array([0.01, -0.01]))
    assert result.target_weights.sum() <= 1.0 + 1e-12
    assert "net_reward" in result.reward_parts


def test_wolf_portfolio_env_reset_step_semantics_with_cash_and_info():
    market = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-31", "2026-01-31", "2026-02-28", "2026-02-28"]),
            "ticker": ["AAA", "BBB", "AAA", "BBB"],
            "sector": ["Tech", "Health", "Tech", "Health"],
            "country": ["DE", "GB", "DE", "GB"],
            "region": ["DACH", "UK", "DACH", "UK"],
            "currency": ["EUR", "GBP", "EUR", "GBP"],
            "target_weight": [0.45, 0.45, 0.45, 0.45],
            "daily_return": [0.01, -0.005, 0.002, 0.003],
            "expected_dividend_return_12m": [0.03, 0.04, 0.03, 0.04],
            "expected_volatility_12m": [0.18, 0.22, 0.18, 0.22],
            "var_5_12m": [-0.15, -0.20, -0.15, -0.20],
            "cvar_5_12m": [-0.20, -0.25, -0.20, -0.25],
            "expected_shortfall_5_12m": [-0.21, -0.26, -0.21, -0.26],
            "dividend_cut_probability": [0.10, 0.15, 0.10, 0.15],
            "liquidity_score": [70, 60, 70, 60],
            "average_daily_value_usd": [20_000_000, 15_000_000, 20_000_000, 15_000_000],
            "regime_suitability_score": [80, 70, 80, 70],
            "narrative_reframing_score": [20, 30, 20, 30],
        }
    )
    env = WolfPortfolioEnv(
        market,
        state_builder=None,
        baseline_policy=None,
        reward_engine=None,
        constraints={"max_delta_weight": 0.01, "max_single_name_weight": 0.70, "maximum_turnover": 0.20, "cash_floor": 0.05},
        config={"rebalance_frequency": "monthly", "risk_free_rate_annual": 0.02},
    )
    observation, reset_info = env.reset(seed=42)
    assert observation.size > 0
    assert reset_info["turnover"] == 0.0
    action = np.zeros(len(env.asset_ids))
    next_observation, reward, terminated, truncated, info = env.step(action)
    assert next_observation.size > 0
    assert isinstance(reward, float)
    assert not terminated
    assert not truncated
    for key in [
        "gross_return",
        "net_return",
        "dividend_income",
        "transaction_cost",
        "commission_cost",
        "spread_cost",
        "half_spread_cost",
        "market_impact_cost",
        "nonlinear_market_impact",
        "currency_conversion_cost",
        "transaction_tax_cost",
        "total_cost",
        "max_participation_rate",
        "turnover",
        "drawdown",
        "VaR_penalty",
        "CVaR_penalty",
        "ES_penalty",
        "dividend_risk_penalty",
        "liquidity_penalty",
        "regime_penalty",
        "narrative_penalty",
        "stress_penalty",
        "constraint_adjustments",
        "fallback_flag",
    ]:
        assert key in info
    assert "CASH" in env.asset_ids


def test_wolf_portfolio_env_chronology_costs_same_step_block_and_fallback():
    market = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-31", "2026-01-31", "2026-02-05", "2026-02-05"]),
            "ticker": ["AAA", "BBB", "AAA", "BBB"],
            "sector": ["Tech", "Health", "Tech", "Health"],
            "country": ["DE", "GB", "DE", "GB"],
            "region": ["DACH", "UK", "DACH", "UK"],
            "currency": ["EUR", "GBP", "EUR", "GBP"],
            "target_weight": [0.50, 0.50, 0.50, 0.50],
            "daily_return": [0.01, 0.00, 0.20, 0.20],
            "expected_dividend_return_12m": [0.00, 0.00, 0.00, 0.00],
            "expected_volatility_12m": [0.18, 0.20, 0.18, 0.20],
            "var_5_12m": [-0.15, -0.18, -0.15, -0.18],
            "cvar_5_12m": [-0.20, -0.22, -0.20, -0.22],
            "expected_shortfall_5_12m": [-0.21, -0.23, -0.21, -0.23],
            "liquidity_score": [80, 80, 80, 80],
            "average_daily_value_usd": [5_000_000, 5_000_000, 5_000_000, 5_000_000],
        }
    )
    env = WolfPortfolioEnv(
        market,
        state_builder=None,
        baseline_policy=None,
        reward_engine=None,
        constraints={"max_delta_weight": 0.01, "max_single_name_weight": 0.70, "maximum_turnover": 0.20},
        config={"rebalance_frequency": "monthly", "initial_nav": 1_000_000, "market_friction": {"commission_bps": 10.0}},
    )
    observation, reset_info = env.reset(seed=7)
    assert reset_info["date"] == pd.Timestamp("2026-01-31")
    assert observation[0, 0] == 0.01

    next_observation, reward, terminated, truncated, info = env.step(np.array([0.01, -0.01, 0.0]))
    assert info["date"] == pd.Timestamp("2026-01-31")
    assert next_observation[0, 0] == 0.20
    assert info["total_cost"] > 0
    assert info["net_return"] < info["gross_return"] + info["dividend_income"]
    assert not terminated
    assert not truncated
    assert isinstance(reward, float)

    _, _, terminated, _, second_info = env.step(np.array([-0.01, 0.01, 0.0]))
    assert second_info["constraint_adjustments"].get("same_day_trade_blocked") == 1.0
    assert second_info["turnover"] == 0.0
    assert terminated

    fallback_env = WolfPortfolioEnv(
        market,
        state_builder=None,
        baseline_policy=None,
        reward_engine=None,
        constraints={"max_delta_weight": 0.02, "max_single_name_weight": 0.20, "maximum_turnover": 0.01},
        config={"rebalance_frequency": "monthly"},
    )
    fallback_env.reset(seed=11)
    _, _, _, _, fallback_info = fallback_env.step(np.array([0.02, 0.02, 0.0]))
    assert fallback_info["fallback_flag"]
