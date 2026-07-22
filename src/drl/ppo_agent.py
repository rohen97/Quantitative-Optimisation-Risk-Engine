from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd

try:
    from stable_baselines3 import PPO

    SB3_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on optional local install
    PPO = None
    SB3_AVAILABLE = False


@dataclass
class PPOTrainingResult:
    seed: int
    action: np.ndarray
    training_reward: float
    validation_reward: float
    policy_type: str = "mock_mlp_ppo"
    deterministic_evaluation: bool = True
    stable_baselines3_available: bool = SB3_AVAILABLE


@dataclass(frozen=True)
class PPOAgentConfig:
    policy: str = "MlpPolicy"
    hidden_layers: tuple[int, int] = (64, 64)
    activation: str = "tanh"
    gamma: float = 0.90
    gae_lambda: float = 0.90
    clip_range: float = 0.25
    learning_rate_start: float = 3e-4
    learning_rate_end: float = 1e-5
    n_epochs: int = 16
    total_timesteps: int = 2048
    deterministic_evaluation: bool = True
    use_stable_baselines: bool = False
    minimum_random_seeds: int = 5


def ppo_config_from_dict(config: dict | None = None) -> PPOAgentConfig:
    """Parse PPO config while keeping dry-run defaults small."""
    raw = (config or {}).get("ppo", config or {})
    return PPOAgentConfig(
        policy=str(raw.get("policy", "MlpPolicy")),
        hidden_layers=tuple(raw.get("hidden_layers", [64, 64])),
        activation=str(raw.get("activation", "tanh")),
        gamma=float(raw.get("gamma", 0.90)),
        gae_lambda=float(raw.get("gae_lambda", 0.90)),
        clip_range=float(raw.get("clip_range", 0.25)),
        learning_rate_start=float(raw.get("learning_rate_start", 3e-4)),
        learning_rate_end=float(raw.get("learning_rate_end", 1e-5)),
        n_epochs=int(raw.get("n_epochs", 16)),
        total_timesteps=int(raw.get("total_timesteps", 2048)),
        deterministic_evaluation=bool(raw.get("deterministic_evaluation", True)),
        use_stable_baselines=bool(raw.get("use_stable_baselines", False)),
        minimum_random_seeds=int(raw.get("minimum_random_seeds", 5)),
    )


def ensure_minimum_seeds(seeds, minimum: int = 5) -> tuple[int, ...]:
    """Ensure PPO comparisons use at least five deterministic seeds."""
    values = [int(seed) for seed in (seeds or [])]
    candidate = 7
    while len(values) < int(minimum):
        if candidate not in values:
            values.append(candidate)
        candidate += 10
    return tuple(values)


def linear_learning_rate_schedule(start: float = 3e-4, end: float = 1e-5) -> Callable[[float], float]:
    """Stable-Baselines3 compatible decaying learning-rate schedule."""
    start = float(start)
    end = float(end)

    def schedule(progress_remaining: float) -> float:
        progress = float(np.clip(progress_remaining, 0.0, 1.0))
        return end + (start - end) * progress

    return schedule


def sb3_policy_kwargs(config: PPOAgentConfig) -> dict[str, Any]:
    """Build SB3 policy kwargs without importing torch at module import time."""
    try:
        import torch
    except ImportError:
        return {"net_arch": list(config.hidden_layers)}
    activation_fn = torch.nn.Tanh if config.activation.lower() == "tanh" else torch.nn.ReLU
    return {"net_arch": list(config.hidden_layers), "activation_fn": activation_fn}


class MockPPOAgent:
    """Deterministic PPO-style policy scaffold for local, no-API DRL research."""

    def __init__(self, seed: int, max_adjustment: float = 0.015) -> None:
        self.seed = int(seed)
        self.max_adjustment = float(max_adjustment)

    def predict(self, asset_data: pd.DataFrame) -> np.ndarray:
        """Generate a bounded active-weight action from conservative signals."""
        rng = np.random.default_rng(self.seed)
        score = asset_data["final_recommendation_score"].fillna(50) / 100
        ret = asset_data["expected_total_return_12m"].fillna(0.05)
        div = asset_data["expected_dividend_return_12m"].fillna(0.03)
        risk = asset_data["expected_volatility_12m"].fillna(0.20) + asset_data["dividend_cut_probability"].fillna(0.10)
        signal = score + ret + div - risk
        z = (signal - signal.mean()) / (signal.std(ddof=0) + 1e-8)
        exploration = rng.normal(0.0, self.max_adjustment / 5, size=len(asset_data))
        return np.clip(z.to_numpy(dtype=float) * self.max_adjustment / 2 + exploration, -self.max_adjustment, self.max_adjustment)


class StableBaselinesPPOAgent:
    """Optional Stable-Baselines3 PPO wrapper with deterministic evaluation."""

    def __init__(self, env, seed: int, config: PPOAgentConfig | dict | None = None) -> None:
        if not SB3_AVAILABLE or PPO is None:
            raise ImportError("stable-baselines3 is unavailable; use MockPPOAgent fallback.")
        self.seed = int(seed)
        self.config = ppo_config_from_dict(config) if not isinstance(config, PPOAgentConfig) else config
        self.env = env
        self.model = PPO(
            self.config.policy,
            env,
            gamma=self.config.gamma,
            gae_lambda=self.config.gae_lambda,
            clip_range=self.config.clip_range,
            learning_rate=linear_learning_rate_schedule(self.config.learning_rate_start, self.config.learning_rate_end),
            n_epochs=self.config.n_epochs,
            seed=self.seed,
            policy_kwargs=sb3_policy_kwargs(self.config),
            verbose=0,
        )

    def train(self, total_timesteps: int | None = None):
        """Train PPO for a small configurable dry-run horizon."""
        self.model.learn(total_timesteps=int(total_timesteps or self.config.total_timesteps))
        return self

    def predict(self, observation) -> np.ndarray:
        """Return deterministic continuous action for evaluation."""
        action, _ = self.model.predict(observation, deterministic=self.config.deterministic_evaluation)
        return np.asarray(action, dtype=float)


def build_ppo_agent(
    seed: int,
    max_adjustment: float,
    config: dict | PPOAgentConfig | None = None,
    env=None,
):
    """Build SB3 PPO when explicitly enabled and available, otherwise mock."""
    parsed = ppo_config_from_dict(config) if not isinstance(config, PPOAgentConfig) else config
    if parsed.use_stable_baselines and SB3_AVAILABLE and env is not None:
        return StableBaselinesPPOAgent(env, seed, parsed)
    return MockPPOAgent(seed=seed, max_adjustment=max_adjustment)
