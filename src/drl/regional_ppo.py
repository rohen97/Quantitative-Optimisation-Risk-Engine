from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib
import json
import logging
import multiprocessing as mp
from pathlib import Path
import time
from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DuckDBRepository
from src.drl.ppo_agent import (
    SB3_AVAILABLE,
    StableBaselinesPPOAgent,
    ensure_minimum_seeds,
    ppo_config_from_dict,
)

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:  # pragma: no cover - optional dependency
    gym = None
    spaces = None


REGIONAL_SLEEVES = (
    "US",
    "UK",
    "DACH",
    "EU ex-DACH",
    "Mainland China",
    "Hong Kong",
)

REGIONAL_FEATURES = (
    "expected_total_return_12m",
    "expected_volatility_12m",
    "cvar_5_12m",
    "final_recommendation_score",
    "momentum_6m",
    "dividend_safety_score",
    "liquidity_score",
    "regime_suitability_score",
)


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegionalScalingStats:
    mean: np.ndarray
    std: np.ndarray
    feature_names: tuple[str, ...] = REGIONAL_FEATURES


@dataclass(frozen=True)
class RegionalSplit:
    train_dates: tuple[pd.Timestamp, ...]
    validation_dates: tuple[pd.Timestamp, ...]
    test_dates: tuple[pd.Timestamp, ...]
    embargo_dates: tuple[pd.Timestamp, ...]


def _safe_numeric(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    values = frame[column] if column in frame else pd.Series(default, index=frame.index)
    return pd.to_numeric(values, errors="coerce").fillna(default)


def _walk_forward_dir(output_dir: Path) -> Path:
    direct = output_dir / "walk_forward"
    if direct.exists():
        return direct
    default = Path("reports/outputs/walk_forward")
    canonical_output = Path("reports/outputs").resolve()
    return default if output_dir.resolve() == canonical_output and default.exists() else direct


def _load_prices(security_ids: list[str], start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if not security_ids:
        return pd.DataFrame()
    repository = DuckDBRepository(load_data_config().duckdb_path, read_only=True)
    return repository.query(
        """
        SELECT security_id, trade_date, adjusted_close
        FROM (
            SELECT
                security_id,
                trade_date,
                COALESCE(adjusted_close, close_price) AS adjusted_close,
                ROW_NUMBER() OVER (
                    PARTITION BY security_id, trade_date
                    ORDER BY
                        CASE WHEN source = 'bloomberg' THEN 1
                             WHEN source = 'yfinance' THEN 2
                             WHEN source = 'eodhd' THEN 3
                             ELSE 4 END,
                        retrieved_at DESC
                ) AS source_row
            FROM prices_daily
            WHERE security_id IN (SELECT UNNEST(?))
              AND trade_date BETWEEN ? AND ?
              AND COALESCE(adjusted_close, close_price) > 0
        )
        WHERE source_row = 1
        ORDER BY security_id, trade_date
        """,
        [security_ids, start.date(), end.date()],
    )


def _forward_returns(weights: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    anchors = [
        pd.Timestamp(value)
        for value in sorted(pd.to_datetime(weights["as_of_date"]).dropna().unique())
    ]
    next_dates = dict(zip(anchors[:-1], anchors[1:]))
    groups = {
        str(security_id): group.sort_values("trade_date").reset_index(drop=True)
        for security_id, group in prices.groupby("security_id", sort=False)
    }
    rows: list[dict[str, object]] = []
    requests = weights[["security_id", "as_of_date"]].drop_duplicates()
    for request in requests.itertuples(index=False):
        as_of = pd.Timestamp(request.as_of_date)
        end = next_dates.get(as_of)
        group = groups.get(str(request.security_id))
        if end is None or group is None:
            continue
        dates = pd.to_datetime(group["trade_date"]).to_numpy(dtype="datetime64[ns]")
        values = pd.to_numeric(group["adjusted_close"], errors="coerce").to_numpy(dtype=float)
        start_position = int(np.searchsorted(dates, np.datetime64(as_of), side="right")) - 1
        end_position = int(np.searchsorted(dates, np.datetime64(pd.Timestamp(end)), side="right")) - 1
        if start_position < 0 or end_position <= start_position:
            continue
        start_value = values[start_position]
        end_value = values[end_position]
        if np.isfinite(start_value) and np.isfinite(end_value) and start_value > 0:
            rows.append(
                {
                    "security_id": str(request.security_id),
                    "as_of_date": as_of,
                    "forward_return": end_value / start_value - 1.0,
                }
            )
    return pd.DataFrame(rows)


def _weighted_value(group: pd.DataFrame, column: str) -> float:
    values = _safe_numeric(group, column, 0.0).to_numpy(dtype=float)
    weights = _safe_numeric(group, "weight", 0.0).clip(lower=0.0).to_numpy(dtype=float)
    valid = np.isfinite(values)
    if not valid.any():
        return 0.0
    denominator = float(weights[valid].sum())
    if denominator <= 0:
        return float(np.mean(values[valid]))
    return float(np.dot(values[valid], weights[valid]) / denominator)


def build_regional_panel(output_dir: str | Path) -> pd.DataFrame:
    """Build dated regional states and next-month outcomes from walk-forward artifacts."""
    artifact_dir = _walk_forward_dir(Path(output_dir))
    weights_path = artifact_dir / "historical_portfolio_weights.parquet"
    if not weights_path.exists():
        return pd.DataFrame()
    weights = pd.read_parquet(weights_path)
    if "strategy" in weights:
        weights = weights.loc[weights["strategy"].eq("wolf_cvar")].copy()
    if weights.empty or "as_of_date" not in weights:
        return pd.DataFrame()
    weights["as_of_date"] = pd.to_datetime(weights["as_of_date"]).dt.normalize()
    weights["weight"] = _safe_numeric(
        weights,
        "weight" if "weight" in weights else "target_weight",
        0.0,
    )
    equity = weights.loc[
        weights["region"].isin(REGIONAL_SLEEVES)
        & weights["security_id"].astype(str).str.upper().ne("CASH")
    ].copy()
    if equity.empty:
        return pd.DataFrame()
    anchors = sorted(equity["as_of_date"].unique())
    prices = _load_prices(
        sorted(equity["security_id"].astype(str).unique()),
        pd.Timestamp(anchors[0]) - pd.Timedelta(days=10),
        pd.Timestamp(anchors[-1]) + pd.Timedelta(days=10),
    )
    outcomes = _forward_returns(equity, prices)
    equity = equity.merge(outcomes, on=["security_id", "as_of_date"], how="left")

    rows: list[dict[str, object]] = []
    for as_of, dated in equity.groupby("as_of_date", sort=True):
        for sleeve in REGIONAL_SLEEVES:
            group = dated.loc[dated["region"].eq(sleeve)]
            baseline_weight = float(_safe_numeric(group, "weight", 0.0).clip(lower=0.0).sum())
            valid_outcomes = group.loc[pd.to_numeric(group["forward_return"], errors="coerce").notna()]
            row: dict[str, object] = {
                "date": pd.Timestamp(as_of),
                "sleeve": sleeve,
                "baseline_weight": baseline_weight,
                "forward_return": _weighted_value(valid_outcomes, "forward_return"),
                "valid_outcome_weight": float(
                    _safe_numeric(valid_outcomes, "weight", 0.0).clip(lower=0.0).sum()
                ),
                "holding_count": int(group["security_id"].nunique()),
            }
            for feature in REGIONAL_FEATURES:
                row[feature] = _weighted_value(group, feature)
            rows.append(row)
    panel = pd.DataFrame(rows)
    if panel.empty:
        return panel
    final_date = panel["date"].max()
    panel = panel.loc[panel["date"].lt(final_date)].copy()
    return panel.sort_values(["date", "sleeve"]).reset_index(drop=True)


def chronological_regional_split(
    dates: list[pd.Timestamp] | pd.Series,
    train_fraction: float = 0.60,
    validation_fraction: float = 0.20,
    embargo_periods: int = 1,
    frozen_test_start: str | pd.Timestamp | None = None,
    frozen_test_end: str | pd.Timestamp | None = None,
    minimum_train_periods: int = 24,
    minimum_validation_periods: int = 6,
    minimum_test_periods: int = 6,
) -> RegionalSplit:
    ordered = tuple(pd.DatetimeIndex(pd.to_datetime(dates)).dropna().sort_values().unique())
    if len(ordered) < (
        minimum_train_periods + minimum_validation_periods + minimum_test_periods
    ):
        return RegionalSplit(tuple(), tuple(), tuple(), tuple())
    embargo = max(int(embargo_periods), 0)
    if frozen_test_start is not None:
        test_start_date = pd.Timestamp(frozen_test_start)
        test_end_date = (
            pd.Timestamp(frozen_test_end)
            if frozen_test_end is not None
            else pd.Timestamp.max
        )
        test_dates = tuple(
            value
            for value in ordered
            if value >= test_start_date and value <= test_end_date
        )
        if len(test_dates) < minimum_test_periods:
            return RegionalSplit(tuple(), tuple(), tuple(), tuple())
        test_start_index = ordered.index(test_dates[0])
        test_embargo_start = max(test_start_index - embargo, 0)
        development = ordered[:test_embargo_start]
        validation_count = max(
            minimum_validation_periods,
            int(len(ordered) * validation_fraction),
        )
        validation_count = min(
            validation_count,
            len(development) - minimum_train_periods - embargo,
        )
        if validation_count < minimum_validation_periods:
            return RegionalSplit(tuple(), tuple(), tuple(), tuple())
        validation_start = len(development) - validation_count
        train_end = max(validation_start - embargo, 0)
        train_dates = ordered[:train_end]
        validation_dates = development[validation_start:]
        if len(train_dates) < minimum_train_periods:
            return RegionalSplit(tuple(), tuple(), tuple(), tuple())
        embargo_dates = (
            ordered[train_end:validation_start]
            + ordered[test_embargo_start:test_start_index]
        )
        return RegionalSplit(
            train_dates=train_dates,
            validation_dates=validation_dates,
            test_dates=test_dates,
            embargo_dates=embargo_dates,
        )
    train_count = max(minimum_train_periods, int(len(ordered) * train_fraction))
    remaining = len(ordered) - train_count - 2 * embargo
    validation_count = max(
        minimum_validation_periods,
        min(int(len(ordered) * validation_fraction), remaining // 2),
    )
    test_count = remaining - validation_count
    if validation_count < minimum_validation_periods or test_count < minimum_test_periods:
        return RegionalSplit(tuple(), tuple(), tuple(), tuple())
    train_end = train_count
    validation_start = train_end + embargo
    validation_end = validation_start + validation_count
    test_start = validation_end + embargo
    embargo_dates = ordered[train_end:validation_start] + ordered[validation_end:test_start]
    return RegionalSplit(
        train_dates=ordered[:train_end],
        validation_dates=ordered[validation_start:validation_end],
        test_dates=ordered[test_start : test_start + test_count],
        embargo_dates=embargo_dates,
    )


def regional_split_from_config(
    panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> RegionalSplit:
    dates = list(pd.DatetimeIndex(panel["date"].unique()).sort_values())
    return chronological_regional_split(
        dates,
        float(config.get("train_fraction", 0.60)),
        float(config.get("validation_fraction", 0.20)),
        int(config.get("embargo_periods", 1)),
        config.get("frozen_test_start"),
        config.get("frozen_test_end"),
        int(config.get("minimum_train_periods", 24)),
        int(config.get("minimum_validation_periods", 6)),
        int(config.get("minimum_test_periods", 6)),
    )


def build_regional_split_manifest(
    panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    split = regional_split_from_config(panel, config)
    columns = [
        column
        for column in (
            "date",
            "sleeve",
            "baseline_weight",
            "forward_return",
            *REGIONAL_FEATURES,
        )
        if column in panel
    ]
    ordered = panel[columns].sort_values(["date", "sleeve"]).reset_index(drop=True)
    row_hashes = pd.util.hash_pandas_object(ordered, index=False).to_numpy(dtype=np.uint64)
    digest = hashlib.sha256(row_hashes.tobytes()).hexdigest()
    rows = []
    for label, values in (
        ("train", split.train_dates),
        ("validation", split.validation_dates),
        ("embargo", split.embargo_dates),
        ("legacy_locked_oos", split.test_dates),
    ):
        rows.append(
            {
                "split": label,
                "start_date": min(values) if values else pd.NaT,
                "end_date": max(values) if values else pd.NaT,
                "observations": len(values),
                "panel_hash_sha256": digest,
                "holdout_label": str(
                    config.get("holdout_label", "legacy_locked_oos")
                ),
                "prospective_holdout_start": config.get(
                    "prospective_holdout_start"
                ),
                "test_period_model_selection_allowed": False,
            }
        )
    return pd.DataFrame(rows)


def fit_regional_scaler(panel: pd.DataFrame, train_dates: tuple[pd.Timestamp, ...]) -> RegionalScalingStats:
    train = panel.loc[panel["date"].isin(train_dates)]
    values = train[list(REGIONAL_FEATURES)].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    mean = values.mean().to_numpy(dtype=float)
    std = values.std(ddof=0).replace(0.0, 1.0).to_numpy(dtype=float)
    return RegionalScalingStats(mean=mean, std=std)


def apply_regional_scaler(panel: pd.DataFrame, scaler: RegionalScalingStats) -> pd.DataFrame:
    output = panel.copy()
    values = output[list(scaler.feature_names)].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    scaled = (values.to_numpy(dtype=float) - scaler.mean) / scaler.std
    for index, feature in enumerate(scaler.feature_names):
        output[f"state_{feature}"] = scaled[:, index]
    return output


_BaseEnv = gym.Env if gym is not None else object


class RegionalResidualEnv(_BaseEnv):
    """Low-dimensional, cost-aware residual allocator over regional sleeves."""

    metadata = {"render_modes": []}

    def __init__(self, panel: pd.DataFrame, constraints: Mapping[str, Any], config: Mapping[str, Any]):
        if gym is None or spaces is None:
            raise ImportError("gymnasium is required for historical regional PPO training.")
        self.panel = panel.sort_values(["date", "sleeve"]).reset_index(drop=True)
        self.constraints = dict(constraints)
        self.config = dict(config)
        self.dates = tuple(pd.DatetimeIndex(self.panel["date"].unique()).sort_values())
        self.max_delta = float(self.constraints.get("max_delta_weight", 0.01))
        self.no_trade_band = float(self.config.get("no_trade_band_weight", 0.002))
        self.turnover_cap = float(self.constraints.get("maximum_turnover", 0.10))
        self.region_cap = float(self.constraints.get("max_region_weight", 0.40))
        self.cash_floor = float(self.constraints.get("cash_floor", 0.0))
        self.action_scale = float(self.config.get("action_scale", 1.0))
        self.action_space = spaces.Box(
            low=-self.max_delta,
            high=self.max_delta,
            shape=(len(REGIONAL_SLEEVES),),
            dtype=np.float32,
        )
        observation_size = len(REGIONAL_SLEEVES) * (2 + len(REGIONAL_FEATURES))
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(observation_size,),
            dtype=np.float32,
        )
        self.step_index = 0
        self.previous_overlay = np.zeros(len(REGIONAL_SLEEVES), dtype=float)
        self.nav = 1.0
        self.peak_nav = 1.0

    def _rows(self) -> pd.DataFrame:
        date_value = self.dates[min(self.step_index, len(self.dates) - 1)]
        return (
            self.panel.loc[self.panel["date"].eq(date_value)]
            .set_index("sleeve")
            .reindex(REGIONAL_SLEEVES)
            .fillna(0.0)
        )

    def current_rows(self) -> pd.DataFrame:
        """Return the current dated sleeve state for deterministic challengers."""
        return self._rows().copy()

    def _observation(self) -> np.ndarray:
        rows = self._rows()
        columns = ["baseline_weight", *[f"state_{name}" for name in REGIONAL_FEATURES]]
        state = rows[columns].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(dtype=float)
        state = np.column_stack([state, self.previous_overlay])
        return state.reshape(-1).astype(np.float32)

    def reset(self, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        del options
        self.step_index = 0
        self.previous_overlay = np.zeros(len(REGIONAL_SLEEVES), dtype=float)
        self.nav = 1.0
        self.peak_nav = 1.0
        return self._observation(), {"date": self.dates[0], "nav": self.nav}

    def project_action(self, action: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
        rows = self._rows()
        baseline = _safe_numeric(rows, "baseline_weight", 0.0).clip(lower=0.0).to_numpy(dtype=float)
        desired = np.clip(np.asarray(action, dtype=float), -self.max_delta, self.max_delta)
        desired *= self.action_scale
        desired[baseline <= 1e-10] = np.minimum(desired[baseline <= 1e-10], 0.0)
        desired_change = desired - self.previous_overlay
        desired[np.abs(desired_change) < self.no_trade_band] = self.previous_overlay[
            np.abs(desired_change) < self.no_trade_band
        ]
        target = np.clip(baseline + desired, 0.0, self.region_cap)
        maximum_equity = max(0.0, 1.0 - self.cash_floor)
        excess = max(float(target.sum()) - maximum_equity, 0.0)
        positive_active = np.clip(target - baseline, 0.0, None)
        if excess > 0 and positive_active.sum() > 0:
            reduction = min(1.0, excess / float(positive_active.sum()))
            target -= positive_active * reduction
        overlay = target - baseline
        cash_overlay = -float(overlay.sum())
        previous_cash_overlay = -float(self.previous_overlay.sum())
        turnover = 0.5 * (
            float(np.abs(overlay - self.previous_overlay).sum())
            + abs(cash_overlay - previous_cash_overlay)
        )
        if turnover > self.turnover_cap > 0:
            ratio = self.turnover_cap / turnover
            overlay = self.previous_overlay + ratio * (overlay - self.previous_overlay)
            target = np.clip(baseline + overlay, 0.0, self.region_cap)
            cash_overlay = -float(overlay.sum())
            turnover = 0.5 * (
                float(np.abs(overlay - self.previous_overlay).sum())
                + abs(cash_overlay - previous_cash_overlay)
            )
        return target, overlay, turnover

    def _cost_rate(self) -> float:
        friction = self.config.get("market_friction", {}) or {}
        bps = (
            float(friction.get("commission_bps", 2.0))
            + float(friction.get("half_spread_bps", 5.0))
            + float(friction.get("impact_coefficient", 10.0))
            + float(friction.get("currency_conversion_bps", 2.0))
        )
        return bps / 10_000.0

    def step(self, action):
        rows = self._rows()
        date_value = self.dates[self.step_index]
        baseline = _safe_numeric(rows, "baseline_weight", 0.0).clip(lower=0.0).to_numpy(dtype=float)
        returns = _safe_numeric(rows, "forward_return", 0.0).to_numpy(dtype=float)
        target, overlay, turnover = self.project_action(np.asarray(action, dtype=float))
        risk_free_monthly = float(self.config.get("risk_free_rate_annual", 0.0)) / 12.0
        baseline_cash = max(0.0, 1.0 - float(baseline.sum()))
        target_cash = max(0.0, 1.0 - float(target.sum()))
        baseline_return = float(np.dot(baseline, returns) + baseline_cash * risk_free_monthly)
        gross_return = float(np.dot(target, returns) + target_cash * risk_free_monthly)
        transaction_cost = turnover * self._cost_rate()
        net_return = gross_return - transaction_cost
        active_return = net_return - baseline_return
        self.nav *= 1.0 + net_return
        self.peak_nav = max(self.peak_nav, self.nav)
        drawdown = self.nav / self.peak_nav - 1.0
        expected_volatility = float(
            np.dot(target, _safe_numeric(rows, "expected_volatility_12m", 0.20).to_numpy(dtype=float))
        )
        expected_cvar = float(
            np.dot(target, _safe_numeric(rows, "cvar_5_12m", -0.25).to_numpy(dtype=float))
        )
        reward_config = self.config.get("regional_reward", {}) or {}
        drawdown_threshold = float(reward_config.get("drawdown_threshold", 0.10))
        tail_loss_threshold = float(reward_config.get("tail_loss_threshold", 0.05))
        expected_cvar_limit = abs(float(reward_config.get("expected_cvar_limit", -0.25)))
        drawdown_excess = max(-drawdown - drawdown_threshold, 0.0)
        realised_tail_loss = max(-net_return - tail_loss_threshold, 0.0)
        active_tail_loss = max(-active_return - tail_loss_threshold, 0.0)
        expected_tail_excess = max(-expected_cvar - expected_cvar_limit, 0.0)
        active_return_component = float(
            reward_config.get("active_return_scale", 100.0)
        ) * active_return
        transaction_cost_penalty = float(
            reward_config.get("transaction_cost_scale", 25.0)
        ) * transaction_cost
        turnover_penalty = float(
            reward_config.get("turnover_scale", 0.05)
        ) * turnover
        drawdown_penalty = float(
            reward_config.get("drawdown_penalty_scale", 0.50)
        ) * drawdown_excess
        tail_penalty = float(
            reward_config.get("tail_loss_penalty_scale", 2.0)
        ) * (realised_tail_loss + active_tail_loss)
        expected_tail_penalty = float(
            reward_config.get("expected_tail_penalty_scale", 0.25)
        ) * expected_tail_excess
        volatility_penalty = float(
            reward_config.get("volatility_penalty_scale", 0.10)
        ) * max(expected_volatility - 0.30, 0.0)
        reward = (
            active_return_component
            - transaction_cost_penalty
            - turnover_penalty
            - drawdown_penalty
            - tail_penalty
            - expected_tail_penalty
            - volatility_penalty
        )
        self.previous_overlay = overlay
        self.step_index += 1
        terminated = self.step_index >= len(self.dates)
        observation = np.zeros(self.observation_space.shape, dtype=np.float32) if terminated else self._observation()
        info = {
            "date": pd.Timestamp(date_value),
            "baseline_return": baseline_return,
            "gross_return": gross_return,
            "net_return": net_return,
            "active_return": active_return,
            "transaction_cost": transaction_cost,
            "incremental_turnover": turnover,
            "drawdown": drawdown,
            "expected_cvar": expected_cvar,
            "active_return_component": active_return_component,
            "transaction_cost_penalty": transaction_cost_penalty,
            "turnover_penalty": turnover_penalty,
            "drawdown_penalty": drawdown_penalty,
            "tail_risk_penalty": tail_penalty + expected_tail_penalty,
            "volatility_penalty": volatility_penalty,
            "constraint_violations": 0,
            "overlay_json": json.dumps(dict(zip(REGIONAL_SLEEVES, map(float, overlay)))),
        }
        return observation, float(reward), terminated, False, info


def evaluate_regional_policy(agent: StableBaselinesPPOAgent, env: RegionalResidualEnv) -> pd.DataFrame:
    observation, _ = env.reset(seed=agent.seed)
    rows = []
    while True:
        action = agent.predict(observation)
        observation, reward, terminated, truncated, info = env.step(action)
        rows.append({**info, "reward": reward})
        if terminated or truncated:
            break
    return pd.DataFrame(rows)


def summarise_regional_path(path: pd.DataFrame) -> dict[str, float]:
    if path.empty:
        return {"observations": 0.0}
    net = _safe_numeric(path, "net_return", 0.0)
    baseline = _safe_numeric(path, "baseline_return", 0.0)
    active = _safe_numeric(path, "active_return", 0.0)

    def sharpe(values: pd.Series) -> float:
        std = float(values.std(ddof=1))
        return float(values.mean() / std * np.sqrt(12.0)) if std > 1e-12 else 0.0

    def cvar(values: pd.Series) -> float:
        count = max(1, int(np.ceil(len(values) * 0.05)))
        return float(values.nsmallest(count).mean())

    nav = (1.0 + net).cumprod()
    baseline_nav = (1.0 + baseline).cumprod()
    active_std = float(active.std(ddof=1))
    active_se = active_std / np.sqrt(len(active)) if len(active) > 1 else 0.0
    return {
        "observations": float(len(path)),
        "total_net_return": float(nav.iloc[-1] - 1.0),
        "baseline_total_return": float(baseline_nav.iloc[-1] - 1.0),
        "net_sharpe": sharpe(net),
        "baseline_sharpe": sharpe(baseline),
        "information_ratio": sharpe(active),
        "maximum_drawdown": float((nav / nav.cummax() - 1.0).min()),
        "baseline_maximum_drawdown": float((baseline_nav / baseline_nav.cummax() - 1.0).min()),
        "cvar": cvar(net),
        "baseline_cvar": cvar(baseline),
        "mean_active_return": float(active.mean()),
        "active_return_ci_lower_95": float(active.mean() - 1.96 * active_se),
        "active_return_ci_upper_95": float(active.mean() + 1.96 * active_se),
        "annualised_incremental_turnover": float(path["incremental_turnover"].sum() * 12.0 / len(path)),
        "transaction_costs": float(path["transaction_cost"].sum()),
        "constraint_violations": float(path["constraint_violations"].sum()),
    }


def build_current_regional_panel(asset_data: pd.DataFrame, baseline_weights: np.ndarray) -> pd.DataFrame:
    current = asset_data.copy()
    current["weight"] = np.asarray(baseline_weights, dtype=float)
    rows = []
    for sleeve in REGIONAL_SLEEVES:
        group = current.loc[current.get("region", pd.Series("", index=current.index)).eq(sleeve)]
        row: dict[str, object] = {
            "date": pd.Timestamp.today().normalize(),
            "sleeve": sleeve,
            "baseline_weight": float(_safe_numeric(group, "weight", 0.0).sum()),
            "forward_return": 0.0,
        }
        for feature in REGIONAL_FEATURES:
            row[feature] = _weighted_value(group, feature)
        rows.append(row)
    return pd.DataFrame(rows)


def map_regional_overlay_to_assets(
    asset_data: pd.DataFrame,
    baseline_weights: np.ndarray,
    overlay: np.ndarray,
) -> np.ndarray:
    actions = np.zeros(len(asset_data), dtype=float)
    baseline = np.asarray(baseline_weights, dtype=float)
    regions = asset_data.get("region", pd.Series("", index=asset_data.index)).astype(str)
    eligible = asset_data.get(
        "eligible_for_optimisation",
        pd.Series(True, index=asset_data.index),
    ).fillna(False).astype(bool)
    scores = _safe_numeric(asset_data, "final_recommendation_score", 0.0).clip(lower=0.0)
    for sleeve, active_weight in zip(REGIONAL_SLEEVES, overlay):
        mask = regions.eq(sleeve).to_numpy() & eligible.to_numpy()
        if not mask.any() or abs(float(active_weight)) <= 1e-12:
            continue
        held = baseline[mask]
        if held.sum() > 1e-12:
            allocation = held / held.sum()
        else:
            opportunity = scores.to_numpy(dtype=float)[mask] + 1e-6
            allocation = opportunity / opportunity.sum()
        actions[np.flatnonzero(mask)] = float(active_weight) * allocation
    return actions


def _train_regional_seed(
    seed: int,
    scaled: pd.DataFrame,
    current: pd.DataFrame,
    split: RegionalSplit,
    asset_data: pd.DataFrame,
    baseline_weights: np.ndarray,
    constraints: Mapping[str, Any],
    environment_config: Mapping[str, Any],
    current_config: Mapping[str, Any],
    ppo_config: Any,
) -> dict[str, object]:
    """Train and evaluate one isolated seed; safe for a spawned worker process."""
    started = time.perf_counter()
    train_panel = scaled.loc[scaled["date"].isin(split.train_dates)].copy()
    validation_panel = scaled.loc[scaled["date"].isin(split.validation_dates)].copy()
    test_panel = scaled.loc[scaled["date"].isin(split.test_dates)].copy()
    train_env = RegionalResidualEnv(train_panel, constraints, environment_config)
    agent = StableBaselinesPPOAgent(train_env, int(seed), ppo_config).train()
    train_path = evaluate_regional_policy(
        agent,
        RegionalResidualEnv(train_panel, constraints, environment_config),
    )
    validation_path = evaluate_regional_policy(
        agent,
        RegionalResidualEnv(validation_panel, constraints, environment_config),
    )
    test_path = evaluate_regional_policy(
        agent,
        RegionalResidualEnv(test_panel, constraints, environment_config),
    )
    train_metrics = summarise_regional_path(train_path)
    validation_metrics = summarise_regional_path(validation_path)
    test_metrics = summarise_regional_path(test_path)

    inference_env = RegionalResidualEnv(current, constraints, current_config)
    observation, _ = inference_env.reset(seed=int(seed))
    regional_action = agent.predict(observation)
    _, overlay, _ = inference_env.project_action(regional_action)
    action = map_regional_overlay_to_assets(asset_data, baseline_weights, overlay)
    row = {
        "seed": int(seed),
        "training_reward": train_metrics.get("information_ratio", 0.0),
        "validation_reward": validation_metrics.get("information_ratio", 0.0),
        "test_reward": test_metrics.get("total_net_return", 0.0)
        - test_metrics.get("baseline_total_return", 0.0),
        "train_start": min(split.train_dates).date().isoformat(),
        "train_end": max(split.train_dates).date().isoformat(),
        "validation_start": min(split.validation_dates).date().isoformat(),
        "validation_end": max(split.validation_dates).date().isoformat(),
        "test_start": min(split.test_dates).date().isoformat(),
        "test_end": max(split.test_dates).date().isoformat(),
        "embargo_periods": int(environment_config.get("embargo_periods", 1)),
        "scaling_mode": "training_only_regional_panel",
        "hyperparameters": ppo_config.__dict__,
        "test_metrics": test_metrics,
        "constraint_violations": int(test_metrics.get("constraint_violations", 0.0)),
        "model_mode": "real",
        "dependency_mode": "stable_baselines3",
        "runtime_seconds": time.perf_counter() - started,
        "random_split_used": False,
        "test_period_model_selection_used": False,
        "validation_information_ratio": validation_metrics.get("information_ratio", 0.0),
        "test_information_ratio": test_metrics.get("information_ratio", 0.0),
        "test_total_net_return": test_metrics.get("total_net_return", 0.0),
        "baseline_test_total_return": test_metrics.get("baseline_total_return", 0.0),
        "test_net_sharpe": test_metrics.get("net_sharpe", 0.0),
        "baseline_test_sharpe": test_metrics.get("baseline_sharpe", 0.0),
        "test_maximum_drawdown": test_metrics.get("maximum_drawdown", 0.0),
        "baseline_test_maximum_drawdown": test_metrics.get("baseline_maximum_drawdown", 0.0),
        "test_cvar": test_metrics.get("cvar", 0.0),
        "baseline_test_cvar": test_metrics.get("baseline_cvar", 0.0),
        "test_expected_shortfall": test_metrics.get("cvar", 0.0),
        "test_observations": int(test_metrics.get("observations", 0.0)),
        "active_return_ci_lower_95": test_metrics.get("active_return_ci_lower_95", 0.0),
        "annualised_incremental_turnover": test_metrics.get(
            "annualised_incremental_turnover", 0.0
        ),
        "transaction_costs": test_metrics.get("transaction_costs", 0.0),
        "regional_overlay": json.dumps(
            dict(zip(REGIONAL_SLEEVES, map(float, overlay)))
        ),
    }
    reward_row = {
        "seed": int(seed),
        "net_total_return_component": test_metrics.get("total_net_return", 0.0),
        "transaction_cost_penalty": test_metrics.get("transaction_costs", 0.0),
        "turnover_penalty": test_metrics.get("annualised_incremental_turnover", 0.0),
        "information_ratio": test_metrics.get("information_ratio", 0.0),
        "tail_risk_penalty": float(test_path.get("tail_risk_penalty", pd.Series(dtype=float)).sum()),
        "drawdown_penalty": float(test_path.get("drawdown_penalty", pd.Series(dtype=float)).sum()),
    }
    test_path = test_path.copy()
    test_path["seed"] = int(seed)
    test_path["split"] = "test"
    return {"row": row, "action": action, "reward": reward_row, "path": test_path}


def train_historical_regional_ppo(
    panel: pd.DataFrame,
    asset_data: pd.DataFrame,
    baseline_weights: np.ndarray,
    constraints: Mapping[str, Any],
    config: Mapping[str, Any],
    action_scale: float = 1.0,
) -> tuple[pd.DataFrame, dict[int, np.ndarray], list[dict[str, float]], pd.DataFrame]:
    if panel.empty or not SB3_AVAILABLE or not ppo_config_from_dict(dict(config)).use_stable_baselines:
        return pd.DataFrame(), {}, [], pd.DataFrame()
    split = regional_split_from_config(panel, config)
    if not split.train_dates:
        return pd.DataFrame(), {}, [], pd.DataFrame()
    scaler = fit_regional_scaler(panel, split.train_dates)
    scaled = apply_regional_scaler(panel, scaler)
    current = apply_regional_scaler(
        build_current_regional_panel(asset_data, baseline_weights),
        scaler,
    )
    ppo_config = ppo_config_from_dict(dict(config))
    seeds = ensure_minimum_seeds(
        config.get("random_seeds", (11, 23, 37, 53, 71)),
        ppo_config.minimum_random_seeds,
    )
    environment_config = dict(config)
    environment_config["action_scale"] = 1.0
    current_config = dict(config)
    current_config["action_scale"] = float(action_scale)
    requested_workers = max(int(config.get("parallel_seed_workers", 1)), 1)
    worker_count = min(requested_workers, len(seeds))
    worker_args = [
        (
            int(seed),
            scaled,
            current,
            split,
            asset_data,
            np.asarray(baseline_weights, dtype=float),
            dict(constraints),
            environment_config,
            current_config,
            ppo_config,
        )
        for seed in seeds
    ]

    def sequential() -> list[dict[str, object]]:
        return [_train_regional_seed(*arguments) for arguments in worker_args]

    results: list[dict[str, object]]
    if worker_count == 1:
        results = sequential()
    else:
        LOGGER.info(
            "Training %s PPO seeds with %s isolated worker processes.",
            len(seeds),
            worker_count,
        )
        try:
            context = mp.get_context("spawn")
            with ProcessPoolExecutor(
                max_workers=worker_count,
                mp_context=context,
                max_tasks_per_child=1,
            ) as executor:
                futures = [executor.submit(_train_regional_seed, *arguments) for arguments in worker_args]
                results = [future.result() for future in as_completed(futures)]
        except Exception as exc:
            LOGGER.warning(
                "Isolated PPO workers failed (%s); retrying deterministically in one process.",
                exc,
            )
            results = sequential()

    results.sort(key=lambda item: int(item["row"]["seed"]))
    rows = [dict(item["row"], parallel_seed_workers=worker_count) for item in results]
    actions = {
        int(item["row"]["seed"]): np.asarray(item["action"], dtype=float)
        for item in results
    }
    reward_rows = [item["reward"] for item in results]
    path_frames = [item["path"] for item in results]

    summary = pd.DataFrame(rows)
    split_manifest = build_regional_split_manifest(panel, config)
    panel_hash = (
        str(split_manifest["panel_hash_sha256"].iloc[0])
        if not split_manifest.empty
        else ""
    )
    summary["panel_hash_sha256"] = panel_hash
    summary["holdout_label"] = str(
        config.get("holdout_label", "legacy_locked_oos")
    )
    summary["prospective_holdout_start"] = config.get(
        "prospective_holdout_start"
    )
    best_seed = int(summary.loc[summary["validation_reward"].idxmax(), "seed"])
    summary["best_validation_score"] = float(summary["validation_reward"].max())
    summary["selected_by_validation"] = summary["seed"].eq(best_seed)
    paths = pd.concat(path_frames, ignore_index=True) if path_frames else pd.DataFrame()
    return summary, actions, reward_rows, paths
