import numpy as np
import pandas as pd

from src.drl.ppo_agent import (
    MockPPOAgent,
    PPOAgentConfig,
    SB3_AVAILABLE,
    build_ppo_agent,
    ensure_minimum_seeds,
    linear_learning_rate_schedule,
    ppo_config_from_dict,
    sb3_policy_kwargs,
)


def test_ppo_optional_import_flag_is_boolean():
    assert isinstance(SB3_AVAILABLE, bool)


def test_ppo_config_defaults_match_dry_run_recommendations():
    cfg = ppo_config_from_dict({})
    assert cfg.hidden_layers == (64, 64)
    assert cfg.activation == "tanh"
    assert cfg.gamma == 0.90
    assert cfg.gae_lambda == 0.90
    assert cfg.clip_range == 0.25
    assert cfg.n_epochs == 16
    assert cfg.total_timesteps < 7_500_000
    assert cfg.minimum_random_seeds == 5


def test_ensure_minimum_seeds_extends_to_five():
    seeds = ensure_minimum_seeds([1, 2], minimum=5)
    assert len(seeds) == 5
    assert seeds[:2] == (1, 2)


def test_learning_rate_schedule_decays():
    schedule = linear_learning_rate_schedule(3e-4, 1e-5)
    assert schedule(1.0) == 3e-4
    assert schedule(0.0) == 1e-5


def test_mock_ppo_agent_is_seed_deterministic_and_continuous():
    data = pd.DataFrame(
        {
            "final_recommendation_score": [80, 50],
            "expected_total_return_12m": [0.08, 0.03],
            "expected_dividend_return_12m": [0.03, 0.02],
            "expected_volatility_12m": [0.18, 0.25],
            "dividend_cut_probability": [0.10, 0.20],
        }
    )
    first = MockPPOAgent(seed=7, max_adjustment=0.01).predict(data)
    second = MockPPOAgent(seed=7, max_adjustment=0.01).predict(data)
    assert np.allclose(first, second)
    assert first.dtype.kind == "f"
    assert np.abs(first).max() <= 0.01


def test_build_ppo_agent_falls_back_without_explicit_sb3_env():
    agent = build_ppo_agent(7, 0.01, PPOAgentConfig(use_stable_baselines=True), env=None)
    assert isinstance(agent, MockPPOAgent)


def test_sb3_policy_kwargs_are_constructible():
    kwargs = sb3_policy_kwargs(PPOAgentConfig())
    assert kwargs["net_arch"] == [64, 64]
