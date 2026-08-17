from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping, Protocol

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from src.drl.regional_ppo import (
    REGIONAL_FEATURES,
    REGIONAL_SLEEVES,
    RegionalResidualEnv,
    apply_regional_scaler,
    fit_regional_scaler,
    regional_split_from_config,
    summarise_regional_path,
)


STATE_COLUMNS = tuple(f"state_{name}" for name in REGIONAL_FEATURES)


class RegionalChallengerPolicy(Protocol):
    def reset(self) -> None: ...

    def action(self, rows: pd.DataFrame) -> np.ndarray: ...

    def observe(self, info: Mapping[str, object]) -> None: ...


def _numeric(frame: pd.DataFrame, column: str, default: float = 0.0) -> np.ndarray:
    values = frame[column] if column in frame else pd.Series(default, index=frame.index)
    return pd.to_numeric(values, errors="coerce").fillna(default).to_numpy(dtype=float)


def _design_matrix(frame: pd.DataFrame) -> np.ndarray:
    states = frame.reindex(columns=STATE_COLUMNS, fill_value=0.0).apply(
        pd.to_numeric,
        errors="coerce",
    ).fillna(0.0).to_numpy(dtype=float)
    sleeves = frame.get("sleeve", pd.Series("", index=frame.index)).astype(str)
    dummies = np.column_stack(
        [sleeves.eq(sleeve).to_numpy(dtype=float) for sleeve in REGIONAL_SLEEVES]
    )
    return np.column_stack([np.ones(len(frame), dtype=float), states, dummies])


def _active_targets(frame: pd.DataFrame) -> np.ndarray:
    returns = pd.to_numeric(frame["forward_return"], errors="coerce")
    weights = pd.to_numeric(frame["baseline_weight"], errors="coerce").fillna(0.0).clip(lower=0.0)
    numerator = (returns.fillna(0.0) * weights).groupby(frame["date"]).transform("sum")
    denominator = weights.groupby(frame["date"]).transform("sum").replace(0.0, np.nan)
    benchmark = (numerator / denominator).fillna(
        returns.groupby(frame["date"]).transform("mean")
    )
    return (returns - benchmark).fillna(0.0).to_numpy(dtype=float)


@dataclass
class RidgeContextualBandit:
    coefficients: np.ndarray
    max_delta: float

    def reset(self) -> None:
        return None

    def action(self, rows: pd.DataFrame) -> np.ndarray:
        predictions = _design_matrix(rows) @ self.coefficients
        baseline = np.clip(_numeric(rows, "baseline_weight", 0.0), 0.0, None)
        denominator = float(baseline.sum())
        centre = (
            float(np.dot(predictions, baseline) / denominator)
            if denominator > 1.0e-12
            else float(predictions.mean())
        )
        active = predictions - centre
        scale = float(np.median(np.abs(active - np.median(active))))
        scale = max(scale, 1.0e-4)
        return self.max_delta * np.tanh(active / (2.0 * scale))

    def observe(self, info: Mapping[str, object]) -> None:
        del info


def fit_contextual_bandit(
    frame: pd.DataFrame,
    ridge_penalty: float,
    max_delta: float,
) -> RidgeContextualBandit:
    x = _design_matrix(frame)
    y = _active_targets(frame)
    penalty = np.eye(x.shape[1], dtype=float) * max(float(ridge_penalty), 0.0)
    penalty[0, 0] = 0.0
    coefficients = np.linalg.pinv(x.T @ x + penalty) @ x.T @ y
    return RidgeContextualBandit(coefficients=coefficients, max_delta=max_delta)


@dataclass
class ConvexResidualAllocator:
    covariance: np.ndarray
    prior_active_return: np.ndarray
    risk_aversion: float
    turnover_penalty: float
    cost_penalty: float
    max_delta: float
    region_cap: float
    previous_overlay: np.ndarray

    def reset(self) -> None:
        self.previous_overlay = np.zeros(len(REGIONAL_SLEEVES), dtype=float)

    def _signal(self, rows: pd.DataFrame) -> np.ndarray:
        signal = (
            0.45 * _numeric(rows, "state_expected_total_return_12m")
            + 0.18 * _numeric(rows, "state_momentum_6m")
            + 0.12 * _numeric(rows, "state_final_recommendation_score")
            + 0.10 * _numeric(rows, "state_dividend_safety_score")
            + 0.08 * _numeric(rows, "state_liquidity_score")
            + 0.12 * _numeric(rows, "state_cvar_5_12m")
            - 0.15 * _numeric(rows, "state_expected_volatility_12m")
            + self.prior_active_return
        )
        return signal - float(signal.mean())

    def action(self, rows: pd.DataFrame) -> np.ndarray:
        signal = self._signal(rows)
        baseline = np.clip(_numeric(rows, "baseline_weight", 0.0), 0.0, None)
        lower = np.maximum(-self.max_delta, -baseline)
        upper = np.minimum(self.max_delta, self.region_cap - baseline)

        def objective(values: np.ndarray) -> float:
            change = values - self.previous_overlay
            smooth_l1 = np.sqrt(np.square(change) + 1.0e-10).sum()
            return float(
                -np.dot(signal, values)
                + self.risk_aversion * values @ self.covariance @ values
                + self.turnover_penalty * np.dot(change, change)
                + self.cost_penalty * smooth_l1
            )

        result = minimize(
            objective,
            np.clip(self.previous_overlay, lower, upper),
            method="SLSQP",
            bounds=list(zip(lower, upper, strict=True)),
            constraints=[{"type": "eq", "fun": lambda values: float(values.sum())}],
            options={"maxiter": 100, "ftol": 1.0e-10},
        )
        if not result.success or result.x is None or not np.isfinite(result.x).all():
            return self.previous_overlay.copy()
        return np.asarray(result.x, dtype=float)

    def observe(self, info: Mapping[str, object]) -> None:
        payload = info.get("overlay_json")
        if not payload:
            return
        values = json.loads(str(payload))
        self.previous_overlay = np.asarray(
            [float(values.get(sleeve, 0.0)) for sleeve in REGIONAL_SLEEVES],
            dtype=float,
        )


def _regional_return_statistics(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    pivot = frame.pivot_table(
        index="date",
        columns="sleeve",
        values="forward_return",
        aggfunc="last",
    ).reindex(columns=REGIONAL_SLEEVES).fillna(0.0)
    values = pivot.to_numpy(dtype=float)
    covariance = np.cov(values, rowvar=False, ddof=1) if len(values) > 1 else np.eye(len(REGIONAL_SLEEVES))
    covariance = np.asarray(covariance, dtype=float)
    diagonal = np.diag(np.diag(covariance))
    covariance = 0.80 * covariance + 0.20 * diagonal + np.eye(len(REGIONAL_SLEEVES)) * 1.0e-6
    mean_return = np.nanmean(values, axis=0)
    prior = mean_return - float(np.mean(mean_return))
    return covariance, prior


def fit_convex_allocator(
    frame: pd.DataFrame,
    constraints: Mapping[str, Any],
    settings: Mapping[str, Any],
    risk_aversion: float,
) -> ConvexResidualAllocator:
    covariance, prior = _regional_return_statistics(frame)
    return ConvexResidualAllocator(
        covariance=covariance,
        prior_active_return=prior,
        risk_aversion=float(risk_aversion),
        turnover_penalty=float(settings.get("turnover_penalty", 2.0)),
        cost_penalty=float(settings.get("cost_penalty", 0.02)),
        max_delta=float(constraints.get("max_delta_weight", 0.01)),
        region_cap=float(constraints.get("max_region_weight", 0.40)),
        previous_overlay=np.zeros(len(REGIONAL_SLEEVES), dtype=float),
    )


def evaluate_challenger(
    policy: RegionalChallengerPolicy,
    panel: pd.DataFrame,
    constraints: Mapping[str, Any],
    config: Mapping[str, Any],
) -> pd.DataFrame:
    env = RegionalResidualEnv(panel, constraints, config)
    policy.reset()
    env.reset()
    rows: list[dict[str, object]] = []
    while True:
        action = policy.action(env.current_rows())
        _, reward, terminated, truncated, info = env.step(action)
        policy.observe(info)
        rows.append({**info, "reward": reward})
        if terminated or truncated:
            break
    return pd.DataFrame(rows)


def _metric_row(
    algorithm: str,
    parameter_name: str,
    parameter_value: float,
    split: str,
    path: pd.DataFrame,
) -> dict[str, object]:
    metrics = summarise_regional_path(path)
    return {
        "algorithm": algorithm,
        "parameter_name": parameter_name,
        "parameter_value": parameter_value,
        "split": split,
        **metrics,
        "test_period_model_selection_used": False,
    }


def _selection_key(row: Mapping[str, object]) -> tuple[float, float, float]:
    return (
        float(row.get("information_ratio", -np.inf)),
        float(row.get("mean_active_return", -np.inf)),
        -float(row.get("annualised_incremental_turnover", np.inf)),
    )


def run_regional_challengers(
    panel: pd.DataFrame,
    constraints: Mapping[str, Any],
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare low-variance challengers using validation-only model selection."""

    split = regional_split_from_config(panel, config)
    if not split.train_dates:
        return pd.DataFrame(), pd.DataFrame()
    scaler = fit_regional_scaler(panel, split.train_dates)
    scaled = apply_regional_scaler(panel, scaler)
    train = scaled.loc[scaled["date"].isin(split.train_dates)].copy()
    validation = scaled.loc[scaled["date"].isin(split.validation_dates)].copy()
    test = scaled.loc[scaled["date"].isin(split.test_dates)].copy()
    development = scaled.loc[
        scaled["date"].isin(split.train_dates + split.validation_dates)
    ].copy()
    algorithms = dict(config.get("algorithms", {}) or {})
    rows: list[dict[str, object]] = []
    paths: list[pd.DataFrame] = []
    selected_validation_rows: list[dict[str, object]] = []
    max_delta = float(constraints.get("max_delta_weight", 0.01))

    bandit_config = dict(algorithms.get("contextual_bandit", {}) or {})
    penalties = [float(value) for value in bandit_config.get("ridge_penalties", [0.1, 1.0, 10.0])]
    bandit_candidates: list[tuple[dict[str, object], float, pd.DataFrame]] = []
    for penalty in penalties:
        policy = fit_contextual_bandit(train, penalty, max_delta)
        path = evaluate_challenger(policy, validation, constraints, config)
        row = _metric_row("contextual_bandit", "ridge_penalty", penalty, "validation", path)
        bandit_candidates.append((row, penalty, path))
        rows.append(row)
    best_bandit = max(bandit_candidates, key=lambda item: _selection_key(item[0]))
    selected_validation_rows.append(best_bandit[0])
    final_bandit = fit_contextual_bandit(development, best_bandit[1], max_delta)
    bandit_test = evaluate_challenger(final_bandit, test, constraints, config)
    rows.append(_metric_row("contextual_bandit", "ridge_penalty", best_bandit[1], "legacy_locked_oos", bandit_test))
    for split_name, path in (("validation", best_bandit[2]), ("legacy_locked_oos", bandit_test)):
        traced = path.copy()
        traced["algorithm"] = "contextual_bandit"
        traced["split"] = split_name
        paths.append(traced)

    convex_config = dict(algorithms.get("convex_residual", {}) or {})
    risk_values = [float(value) for value in convex_config.get("risk_aversion_values", [1.0, 3.0, 10.0])]
    convex_candidates: list[tuple[dict[str, object], float, pd.DataFrame]] = []
    for risk_aversion in risk_values:
        policy = fit_convex_allocator(train, constraints, convex_config, risk_aversion)
        path = evaluate_challenger(policy, validation, constraints, config)
        row = _metric_row("convex_residual", "risk_aversion", risk_aversion, "validation", path)
        convex_candidates.append((row, risk_aversion, path))
        rows.append(row)
    best_convex = max(convex_candidates, key=lambda item: _selection_key(item[0]))
    selected_validation_rows.append(best_convex[0])
    final_convex = fit_convex_allocator(development, constraints, convex_config, best_convex[1])
    convex_test = evaluate_challenger(final_convex, test, constraints, config)
    rows.append(_metric_row("convex_residual", "risk_aversion", best_convex[1], "legacy_locked_oos", convex_test))
    for split_name, path in (("validation", best_convex[2]), ("legacy_locked_oos", convex_test)):
        traced = path.copy()
        traced["algorithm"] = "convex_residual"
        traced["split"] = split_name
        paths.append(traced)

    selected_algorithm = max(selected_validation_rows, key=_selection_key)["algorithm"]
    comparison = pd.DataFrame(rows)
    comparison["selected_parameter_by_validation"] = False
    for selected in selected_validation_rows:
        mask = (
            comparison["algorithm"].eq(selected["algorithm"])
            & comparison["parameter_value"].eq(selected["parameter_value"])
        )
        comparison.loc[mask, "selected_parameter_by_validation"] = True
    comparison["selected_challenger_by_validation"] = comparison["algorithm"].eq(
        selected_algorithm
    )
    comparison["deployment_status"] = "research_only_pending_prospective_shadow"
    return comparison, pd.concat(paths, ignore_index=True) if paths else pd.DataFrame()
