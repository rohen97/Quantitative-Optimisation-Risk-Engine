from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd

from src.drl.action_projection import ProjectionResult, project_to_feasible_set, project_weights
from src.drl.market_friction import calculate_market_friction_costs
from src.drl.reward_engine import reward_decomposition

try:
    import gymnasium as gym
except Exception:  # pragma: no cover - depends on optional local install
    gym = None


@dataclass
class MarketReplayResult:
    target_weights: np.ndarray
    reward: float
    reward_parts: dict[str, float]
    projection_report: pd.DataFrame


class DRLMarketEnvironment:
    """Market replay environment with long-only constrained action projection."""

    def __init__(
        self,
        asset_data: pd.DataFrame,
        baseline_weights: np.ndarray,
        eligibility_mask: np.ndarray,
        constraints: dict | None = None,
        config: dict | None = None,
    ) -> None:
        self.asset_data = asset_data.reset_index(drop=True)
        self.baseline_weights = np.asarray(baseline_weights, dtype=float)
        self.eligibility_mask = np.asarray(eligibility_mask, dtype=bool)
        self.constraints = constraints or {}
        self.config = config or {}

    def step(self, action: np.ndarray, current_weights: np.ndarray | None = None) -> MarketReplayResult:
        """Project an action, calculate frictions and produce a reward."""
        current = np.asarray(current_weights if current_weights is not None else self.baseline_weights, dtype=float)
        projected, projection_report = project_to_feasible_set(
            self.baseline_weights,
            action,
            self.asset_data,
            self.eligibility_mask,
            self.constraints,
            cash_weight=float(self.config.get("cash_weight", 0.0)),
        )
        frictions = calculate_market_friction_costs(
            projected,
            current,
            self.asset_data,
            float(self.config.get("initial_nav", 1.0)),
            self.config,
        )
        liquidity_penalty = float(
            (projected * (1 / self.asset_data["liquidity_score"].fillna(50).clip(lower=1))).sum()
            * self.config.get("liquidity_penalty_lambda", 0.10)
        )
        expected_return = float((projected * self.asset_data["expected_total_return_12m"].fillna(0.0)).sum())
        dividend = float((projected * self.asset_data["expected_dividend_return_12m"].fillna(0.0)).sum())
        volatility = float((projected * self.asset_data["expected_volatility_12m"].fillna(0.20)).sum())
        cvar = float((projected * self.asset_data["cvar_5_12m"].fillna(-0.25)).sum())
        drawdown = -float((projected * self.asset_data["large_drawdown_probability_12m"].fillna(0.20)).sum())
        parts = reward_decomposition(
            expected_return,
            dividend,
            volatility,
            cvar,
            drawdown,
            frictions.turnover,
            frictions.commission_cost + frictions.nonlinear_market_impact + frictions.currency_conversion_cost,
            frictions.half_spread_cost,
            liquidity_penalty,
            self.config,
        )
        return MarketReplayResult(projected, float(parts["net_reward"]), parts, projection_report)


class _FallbackEnv:
    """Tiny Gymnasium-compatible base class when gymnasium is unavailable."""

    metadata: dict[str, Any] = {}

    def reset(self, seed: int | None = None):
        raise NotImplementedError

    def step(self, action):
        raise NotImplementedError


_BaseEnv = gym.Env if gym is not None else _FallbackEnv


class WolfPortfolioEnv(_BaseEnv):
    """Dependency-light portfolio allocation environment.

    The agent proposes bounded residual changes relative to a constrained
    optimiser baseline. Hard constraints are applied after every action.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        market_data,
        state_builder: Callable | None,
        baseline_policy,
        reward_engine,
        constraints: dict,
        config: dict,
    ) -> None:
        self.market_data = self._normalise_market_data(market_data)
        self.state_builder = state_builder
        self.baseline_policy = baseline_policy
        self.reward_engine = reward_engine
        self.constraints = constraints or {}
        self.config = config or {}
        self.decision_dates = sorted(self.market_data["date"].drop_duplicates())
        self.asset_metadata = self._asset_metadata()
        self.asset_ids = tuple(self.asset_metadata["ticker"].astype(str))
        self.eligibility_mask = self._eligibility_mask()
        self.baseline_weights = self._initial_baseline_weights()
        self.current_weights = self.baseline_weights.copy()
        self.step_index = 0
        self.nav = float(self.config.get("initial_nav", 1.0))
        self.peak_nav = self.nav
        self.last_trade_date = None
        self.rng = np.random.default_rng(None)
        if gym is not None:
            try:
                from gymnasium import spaces

                n_assets = len(self.asset_ids)
                max_delta = float(self.constraints.get("max_delta_weight", self.config.get("max_adjustment", 0.01)))
                self.action_space = spaces.Box(low=-max_delta, high=max_delta, shape=(n_assets,), dtype=np.float32)
                self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(n_assets,), dtype=np.float32)
            except Exception:
                self.action_space = None
                self.observation_space = None

    @staticmethod
    def _normalise_market_data(market_data) -> pd.DataFrame:
        data = market_data.copy() if isinstance(market_data, pd.DataFrame) else pd.DataFrame(market_data)
        if "date" not in data:
            data["date"] = pd.date_range("2026-01-31", periods=len(data), freq="ME")
        data["date"] = pd.to_datetime(data["date"])
        if "ticker" not in data:
            data["ticker"] = [f"ASSET_{i:03d}" for i in range(len(data))]
        if not data["ticker"].astype(str).str.upper().eq("CASH").any():
            cash_rows = []
            for date in data["date"].drop_duplicates():
                row = {column: 0.0 for column in data.columns}
                row.update(
                    {
                        "date": date,
                        "ticker": "CASH",
                        "sector": "Cash",
                        "country": "Cash",
                        "region": "Cash",
                        "currency": "USD",
                        "asset_class": "cash",
                        "eligible_for_drl": True,
                        "eligible_for_optimisation": True,
                        "liquidity_score": 100.0,
                        "average_daily_value_usd": 1_000_000_000.0,
                    }
                )
                cash_rows.append(row)
            data = pd.concat([data, pd.DataFrame(cash_rows)], ignore_index=True)
        return data.sort_values(["date", "ticker"]).reset_index(drop=True)

    @staticmethod
    def _numeric_vector(rows: pd.DataFrame, column: str, default: float = 0.0) -> np.ndarray:
        if column in rows:
            values = rows[column]
        else:
            values = pd.Series(default, index=rows.index)
        return pd.to_numeric(values, errors="coerce").fillna(default).to_numpy(dtype=float)

    def _asset_metadata(self) -> pd.DataFrame:
        columns = [
            "ticker",
            "sector",
            "country",
            "region",
            "currency",
            "asset_class",
            "average_daily_value_usd",
            "liquidity_score",
        ]
        data = self.market_data.drop_duplicates("ticker").copy()
        for column in columns:
            if column not in data:
                data[column] = "Unknown" if column not in {"average_daily_value_usd", "liquidity_score"} else 50.0
        return data[columns].reset_index(drop=True)

    def _eligibility_mask(self) -> np.ndarray:
        def bool_array(values: pd.Series) -> np.ndarray:
            return values.map(lambda value: str(value).lower() in {"true", "1", "yes"} if not isinstance(value, bool) else value).to_numpy(dtype=bool)

        if "eligible_for_drl" in self.asset_metadata:
            return bool_array(self.asset_metadata["eligible_for_drl"])
        if "eligible_for_optimisation" in self.market_data:
            return bool_array(self.market_data.drop_duplicates("ticker")["eligible_for_optimisation"])
        return np.ones(len(self.asset_metadata), dtype=bool)

    def _initial_baseline_weights(self) -> np.ndarray:
        if callable(self.baseline_policy):
            weights = np.asarray(self.baseline_policy(self.asset_metadata), dtype=float)
        elif isinstance(self.baseline_policy, pd.DataFrame) and "target_weight" in self.baseline_policy:
            weights = self.baseline_policy.drop_duplicates("ticker")["target_weight"].to_numpy(dtype=float)
        elif isinstance(self.baseline_policy, np.ndarray):
            weights = np.asarray(self.baseline_policy, dtype=float)
        elif "baseline_weight" in self.market_data:
            weights = self.market_data.drop_duplicates("ticker")["baseline_weight"].to_numpy(dtype=float)
        elif "target_weight" in self.market_data:
            weights = self.market_data.drop_duplicates("ticker")["target_weight"].to_numpy(dtype=float)
        else:
            weights = np.ones(len(self.asset_metadata), dtype=float)
        if len(weights) != len(self.asset_metadata):
            aligned = (
                self.market_data.drop_duplicates("ticker")
                .set_index("ticker")
                .reindex(self.asset_ids)
                .get("target_weight", pd.Series(0.0, index=self.asset_ids))
            )
            weights = pd.to_numeric(aligned, errors="coerce").fillna(0.0).to_numpy(dtype=float)
        weights = np.nan_to_num(weights, nan=0.0, posinf=0.0, neginf=0.0).clip(min=0.0)
        total = float(weights.sum())
        return weights / total if total > 0 else np.ones(len(weights), dtype=float) / len(weights)

    def _rows_for_step(self, step_index: int) -> pd.DataFrame:
        date = self.decision_dates[min(step_index, len(self.decision_dates) - 1)]
        rows = self.market_data[self.market_data["date"].eq(date)].set_index("ticker").reindex(self.asset_ids).reset_index()
        return rows.fillna(0.0)

    def _observation(self) -> np.ndarray:
        rows = self._rows_for_step(self.step_index)
        if self.state_builder is not None:
            try:
                state = self.state_builder(rows, self.current_weights)
                if hasattr(state, "observation"):
                    return np.asarray(state.observation, dtype=float)
                return np.asarray(state, dtype=float)
            except TypeError:
                pass
        feature_cols = [
            col
            for col in [
                "daily_return",
                "expected_total_return_12m",
                "expected_dividend_return_12m",
                "expected_volatility_12m",
                "liquidity_score",
            ]
            if col in rows
        ]
        if not feature_cols:
            return self.current_weights.astype(float)
        return rows[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(dtype=float)

    def reset(self, seed: int | None = None, options: dict | None = None):
        del options
        self.rng = np.random.default_rng(seed)
        self.step_index = 0
        self.nav = float(self.config.get("initial_nav", 1.0))
        self.peak_nav = self.nav
        self.current_weights = self.baseline_weights.copy()
        self.last_trade_date = None
        return self._observation(), {"nav": self.nav, "date": self.decision_dates[0], "turnover": 0.0}

    def _rebalance_allowed(self, current_date: pd.Timestamp) -> bool:
        if self.last_trade_date is None:
            return True
        frequency = str(self.config.get("rebalance_frequency", "monthly")).lower()
        min_days = 63 if frequency == "quarterly" else 20
        return (current_date - self.last_trade_date).days >= min_days

    def _period_return(self, weights: np.ndarray, rows: pd.DataFrame) -> tuple[float, float]:
        daily_return = self._numeric_vector(rows, "daily_return", 0.0)
        dividend = self._numeric_vector(rows, "dividend_return", 0.0)
        if not np.any(dividend):
            dividend = self._numeric_vector(rows, "expected_dividend_return_12m", 0.0)
        risk_free = float(self.config.get("risk_free_rate_annual", 0.02)) / 252
        cash_weight = max(0.0, 1.0 - float(weights.sum()))
        gross = float((weights * daily_return).sum() + cash_weight * risk_free)
        dividend_income = float((weights * dividend).sum() / 252)
        return gross, dividend_income

    def _costs(self, projected: np.ndarray, previous: np.ndarray, rows: pd.DataFrame) -> dict[str, float]:
        friction = calculate_market_friction_costs(projected, previous, rows, max(float(self.config.get("initial_nav", self.nav)), 1.0), self.config)
        return {
            "turnover": friction.turnover,
            "traded_notional": friction.traded_notional,
            "transaction_cost": friction.commission_cost,
            "commission_cost": friction.commission_cost,
            "spread_cost": friction.half_spread_cost,
            "half_spread_cost": friction.half_spread_cost,
            "market_impact_cost": friction.nonlinear_market_impact,
            "nonlinear_market_impact": friction.nonlinear_market_impact,
            "currency_conversion_cost": friction.currency_conversion_cost,
            "transaction_tax_cost": friction.transaction_tax_cost,
            "total_cost": friction.total_cost,
            "max_participation_rate": friction.max_participation_rate,
        }

    def _penalties(self, weights: np.ndarray, rows: pd.DataFrame) -> dict[str, float]:
        def weighted(column: str, default: float = 0.0) -> float:
            values = self._numeric_vector(rows, column, default)
            return float((weights * values).sum())

        return {
            "VaR_penalty": abs(min(weighted("var_5_12m", -0.15), 0.0)),
            "CVaR_penalty": abs(min(weighted("cvar_5_12m", -0.25), 0.0)),
            "ES_penalty": abs(min(weighted("expected_shortfall_5_12m", -0.25), 0.0)),
            "dividend_risk_penalty": weighted("dividend_cut_probability", 0.10),
            "liquidity_penalty": float((weights * (1 / np.clip(self._numeric_vector(rows, "liquidity_score", 50), 1.0, None))).sum()),
            "regime_penalty": 1.0 - weighted("regime_suitability_score", 50.0) / 100,
            "narrative_penalty": weighted("narrative_reframing_score", 50.0) / 100,
            "stress_penalty": abs(min(weighted("worst_stress_scenario_loss", 0.0), 0.0)),
        }

    def step(self, action):
        current_date = self.decision_dates[self.step_index]
        rows = self._rows_for_step(self.step_index)
        previous_weights = self.current_weights.copy()
        if self._rebalance_allowed(current_date):
            projection: ProjectionResult = project_weights(
                self.baseline_weights,
                np.asarray(action, dtype=float),
                self.eligibility_mask,
                self.asset_metadata,
                previous_weights,
                self.constraints,
            )
            projected = projection.projected_weights
            self.last_trade_date = current_date
        else:
            projection = ProjectionResult(
                previous_weights,
                previous_weights,
                previous_weights,
                {"same_day_trade_blocked": 1.0},
                feasible=True,
                fallback_used=False,
            )
            projected = previous_weights
        gross_return, dividend_income = self._period_return(projected, rows)
        costs = self._costs(projected, previous_weights, rows)
        net_return = gross_return + dividend_income - costs["total_cost"]
        self.nav *= 1.0 + net_return
        self.peak_nav = max(self.peak_nav, self.nav)
        drawdown = self.nav / self.peak_nav - 1.0
        penalties = self._penalties(projected, rows)
        reward_parts = reward_decomposition(
            net_return,
            dividend_income,
            weighted_volatility := float((projected * self._numeric_vector(rows, "expected_volatility_12m", 0.20)).sum()),
            -penalties["CVaR_penalty"],
            drawdown,
            costs["turnover"],
            costs["commission_cost"] + costs["market_impact_cost"] + costs["currency_conversion_cost"] + costs["transaction_tax_cost"],
            costs["spread_cost"],
            penalties["liquidity_penalty"],
            self.config,
        )
        reward = float(reward_parts["net_reward"] - penalties["regime_penalty"] - penalties["narrative_penalty"] - penalties["stress_penalty"])
        self.current_weights = projected
        self.step_index += 1
        terminated = self.step_index >= len(self.decision_dates)
        truncated = False
        observation = self._observation() if not terminated else np.zeros_like(self._observation())
        info = {
            "date": current_date,
            "gross_return": gross_return,
            "net_return": net_return,
            "dividend_income": dividend_income,
            "drawdown": drawdown,
            "weighted_volatility": weighted_volatility,
            "constraint_adjustments": projection.constraint_adjustments,
            "fallback_flag": projection.fallback_used,
            **costs,
            **penalties,
        }
        return observation, reward, terminated, truncated, info
