from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.optimisation.constraints import apply_diversification_caps


@dataclass(frozen=True)
class ProjectionResult:
    raw_weights: np.ndarray
    masked_weights: np.ndarray
    projected_weights: np.ndarray
    constraint_adjustments: dict[str, float]
    feasible: bool
    fallback_used: bool


def normalise_long_only(weights: np.ndarray) -> np.ndarray:
    """Clip to long-only and normalise to one when possible."""
    clipped = np.asarray(weights, dtype=float)
    clipped = np.nan_to_num(clipped, nan=0.0, posinf=0.0, neginf=0.0).clip(min=0.0)
    total = float(clipped.sum())
    return clipped / total if total > 0 else clipped


def bounded_adjustment(action: np.ndarray, max_adjustment: float) -> np.ndarray:
    """Limit agent action to a bounded active-weight adjustment."""
    return np.asarray(action, dtype=float).clip(-float(max_adjustment), float(max_adjustment))


def bounded_residual_action(raw_action: np.ndarray, max_delta_weight: float) -> np.ndarray:
    """Bound each residual action component to the allowed active-weight range."""
    raw_action = np.asarray(raw_action, dtype=float)
    return np.clip(raw_action, -float(max_delta_weight), float(max_delta_weight))


def _metadata(asset_metadata) -> pd.DataFrame:
    if isinstance(asset_metadata, pd.DataFrame):
        return asset_metadata.reset_index(drop=True).copy()
    return pd.DataFrame(asset_metadata).reset_index(drop=True)


def _cash_index(meta: pd.DataFrame) -> int | None:
    if "ticker" in meta:
        matches = meta.index[meta["ticker"].astype(str).str.upper().eq("CASH")]
        if len(matches):
            return int(matches[0])
    if "asset_class" in meta:
        matches = meta.index[meta["asset_class"].astype(str).str.lower().eq("cash")]
        if len(matches):
            return int(matches[0])
    return None


def _as_array(values: np.ndarray, n: int, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.shape[0] != n:
        raise ValueError(f"{name} length {array.shape[0]} does not match asset count {n}.")
    return np.nan_to_num(array, nan=0.0, posinf=0.0, neginf=0.0)


def _group_cap(weights: np.ndarray, meta: pd.DataFrame, column: str, cap: float, cash_idx: int | None) -> np.ndarray:
    if column not in meta or cap >= 1:
        return weights
    adjusted = weights.copy()
    for _, idx in meta.groupby(column).groups.items():
        idx = np.asarray(list(idx), dtype=int)
        if cash_idx is not None:
            idx = idx[idx != cash_idx]
        group_weight = float(adjusted[idx].sum()) if len(idx) else 0.0
        if group_weight > cap and group_weight > 0:
            adjusted[idx] *= cap / group_weight
    return adjusted


def _normalise_with_cash(weights: np.ndarray, cash_idx: int | None, cash_floor: float) -> np.ndarray:
    adjusted = weights.clip(min=0.0)
    if cash_idx is None:
        return normalise_long_only(adjusted)
    cash_floor = float(np.clip(cash_floor, 0.0, 1.0))
    non_cash = np.array([i for i in range(len(adjusted)) if i != cash_idx], dtype=int)
    risky_total = float(adjusted[non_cash].sum())
    max_risky = max(0.0, 1.0 - cash_floor)
    if risky_total > max_risky and risky_total > 0:
        adjusted[non_cash] *= max_risky / risky_total
    adjusted[cash_idx] = max(float(adjusted[cash_idx]), cash_floor)
    total = float(adjusted.sum())
    if total > 1 and risky_total > 0:
        adjusted[non_cash] *= max(0.0, 1.0 - adjusted[cash_idx]) / float(adjusted[non_cash].sum())
    adjusted[cash_idx] = max(0.0, 1.0 - float(adjusted[non_cash].sum()))
    return adjusted


def _apply_position_caps(weights: np.ndarray, meta: pd.DataFrame, constraints: dict, cash_idx: int | None) -> np.ndarray:
    max_weight = float(constraints.get("max_single_name_weight", constraints.get("max_position_weight", 1.0)))
    adjusted = weights.copy()
    for i in range(len(adjusted)):
        if cash_idx is not None and i == cash_idx:
            continue
        adjusted[i] = min(adjusted[i], max_weight)
    return adjusted


def _apply_liquidity_limits(
    weights: np.ndarray,
    current_weights: np.ndarray,
    meta: pd.DataFrame,
    constraints: dict,
    cash_idx: int | None,
) -> np.ndarray:
    if "average_daily_value_usd" not in meta:
        return weights
    nav = float(constraints.get("portfolio_nav_usd", constraints.get("portfolio_nav_usd_fallback", 100_000_000)))
    max_days = float(constraints.get("max_liquidity_days_to_trade", constraints.get("maximum_liquidity_days_to_trade", 5.0)))
    if nav <= 0 or max_days <= 0:
        return weights
    adv_weight = pd.to_numeric(meta["average_daily_value_usd"], errors="coerce").fillna(0.0).to_numpy(dtype=float) * max_days / nav
    adjusted = weights.copy()
    for i in range(len(adjusted)):
        if cash_idx is not None and i == cash_idx:
            continue
        max_trade = max(float(adv_weight[i]), 0.0)
        delta = adjusted[i] - current_weights[i]
        if abs(delta) > max_trade:
            adjusted[i] = current_weights[i] + np.sign(delta) * max_trade
    return adjusted.clip(min=0.0)


def _apply_turnover_cap(weights: np.ndarray, current_weights: np.ndarray, constraints: dict) -> np.ndarray:
    cap = float(constraints.get("maximum_turnover", constraints.get("turnover_cap", 1.0)))
    turnover = float(np.abs(weights - current_weights).sum())
    if turnover <= cap or turnover <= 0:
        return weights
    return current_weights + (weights - current_weights) * (cap / turnover)


def _iterative_projection(
    masked_weights: np.ndarray,
    eligibility_mask: np.ndarray,
    meta: pd.DataFrame,
    current_weights: np.ndarray,
    constraints: dict,
    cash_idx: int | None,
) -> np.ndarray:
    cash_floor = float(constraints.get("cash_floor", constraints.get("minimum_cash_weight", 0.0)))
    adjusted = masked_weights.copy().clip(min=0.0)
    for _ in range(8):
        adjusted = np.where(eligibility_mask, adjusted, 0.0)
        adjusted = _apply_position_caps(adjusted, meta, constraints, cash_idx)
        adjusted = _group_cap(adjusted, meta, "sector", float(constraints.get("max_sector_weight", 1.0)), cash_idx)
        adjusted = _group_cap(adjusted, meta, "country", float(constraints.get("max_country_weight", 1.0)), cash_idx)
        adjusted = _group_cap(adjusted, meta, "region", float(constraints.get("max_region_weight", 1.0)), cash_idx)
        adjusted = _group_cap(adjusted, meta, "currency", float(constraints.get("max_currency_weight", 1.0)), cash_idx)
        adjusted = _apply_liquidity_limits(adjusted, current_weights, meta, constraints, cash_idx)
        adjusted = _apply_turnover_cap(adjusted, current_weights, constraints)
        adjusted = np.where(eligibility_mask, adjusted, 0.0)
        adjusted = _normalise_with_cash(adjusted, cash_idx, cash_floor)
    return adjusted


def _is_feasible(
    weights: np.ndarray,
    eligibility_mask: np.ndarray,
    meta: pd.DataFrame,
    current_weights: np.ndarray,
    constraints: dict,
    cash_idx: int | None,
) -> bool:
    tol = 1e-6
    if np.any(weights < -tol) or abs(float(weights.sum()) - 1.0) > 1e-5:
        return False
    if np.any(weights[~eligibility_mask] > tol):
        return False
    max_weight = float(constraints.get("max_single_name_weight", constraints.get("max_position_weight", 1.0)))
    non_cash = [i for i in range(len(weights)) if i != cash_idx]
    if non_cash and np.any(weights[non_cash] > max_weight + tol):
        return False
    for column, key in [
        ("sector", "max_sector_weight"),
        ("country", "max_country_weight"),
        ("region", "max_region_weight"),
        ("currency", "max_currency_weight"),
    ]:
        if column in meta:
            cap = float(constraints.get(key, 1.0))
            for _, idx in meta.groupby(column).groups.items():
                idx = [i for i in idx if i != cash_idx]
                if idx and float(weights[idx].sum()) > cap + tol:
                    return False
    turnover_cap = float(constraints.get("maximum_turnover", constraints.get("turnover_cap", 1.0)))
    if float(np.abs(weights - current_weights).sum()) > turnover_cap + 1e-5:
        return False
    cash_floor = float(constraints.get("cash_floor", constraints.get("minimum_cash_weight", 0.0)))
    if cash_idx is not None and weights[cash_idx] + tol < cash_floor:
        return False
    return True


def _scipy_projection(
    raw_weights: np.ndarray,
    eligibility_mask: np.ndarray,
    meta: pd.DataFrame,
    current_weights: np.ndarray,
    constraints: dict,
    cash_idx: int | None,
) -> np.ndarray | None:
    try:
        from scipy.optimize import minimize
    except Exception:
        return None
    n = len(raw_weights)
    max_weight = float(constraints.get("max_single_name_weight", constraints.get("max_position_weight", 1.0)))
    cash_floor = float(constraints.get("cash_floor", constraints.get("minimum_cash_weight", 0.0)))
    bounds = []
    for i in range(n):
        if not eligibility_mask[i]:
            bounds.append((0.0, 0.0))
        elif cash_idx is not None and i == cash_idx:
            bounds.append((cash_floor, 1.0))
        else:
            bounds.append((0.0, max_weight))
    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    turnover_cap = float(constraints.get("maximum_turnover", constraints.get("turnover_cap", 1.0)))
    cons.append({"type": "ineq", "fun": lambda w: turnover_cap - np.sum(np.abs(w - current_weights))})
    for column, key in [
        ("sector", "max_sector_weight"),
        ("country", "max_country_weight"),
        ("region", "max_region_weight"),
        ("currency", "max_currency_weight"),
    ]:
        if column in meta:
            cap = float(constraints.get(key, 1.0))
            for _, group_idx in meta.groupby(column).groups.items():
                idx = np.asarray([i for i in group_idx if i != cash_idx], dtype=int)
                if len(idx):
                    cons.append({"type": "ineq", "fun": lambda w, idx=idx, cap=cap: cap - np.sum(w[idx])})
    start = _iterative_projection(raw_weights, eligibility_mask, meta, current_weights, constraints, cash_idx)
    result = minimize(lambda w: float(np.square(w - raw_weights).sum()), start, method="SLSQP", bounds=bounds, constraints=cons, options={"maxiter": 200, "ftol": 1e-10})
    if not result.success:
        return None
    projected = np.asarray(result.x, dtype=float)
    return projected if _is_feasible(projected, eligibility_mask, meta, current_weights, constraints, cash_idx) else None


def project_weights(
    baseline_weights: np.ndarray,
    residual_action: np.ndarray,
    eligibility_mask: np.ndarray,
    asset_metadata,
    current_weights: np.ndarray,
    constraints: dict,
) -> ProjectionResult:
    """Project a residual DRL action onto the feasible portfolio set."""
    meta = _metadata(asset_metadata)
    n = len(meta)
    baseline = _as_array(baseline_weights, n, "baseline_weights")
    current = _as_array(current_weights, n, "current_weights")
    mask = np.asarray(eligibility_mask, dtype=bool)
    if mask.shape[0] != n:
        raise ValueError(f"eligibility_mask length {mask.shape[0]} does not match asset count {n}.")
    cash_idx = _cash_index(meta)
    if cash_idx is not None:
        mask[cash_idx] = True
    max_delta = float(constraints.get("max_delta_weight", constraints.get("max_drl_adjustment", constraints.get("max_adjustment", 0.01))))
    bounded = bounded_residual_action(residual_action, max_delta)
    if bounded.shape[0] != n:
        raise ValueError(f"residual_action length {bounded.shape[0]} does not match asset count {n}.")
    raw_weights = normalise_long_only(baseline + bounded)
    masked_weights = np.where(mask, raw_weights, 0.0)
    if cash_idx is not None:
        masked_weights[cash_idx] = max(masked_weights[cash_idx], float(constraints.get("cash_floor", constraints.get("minimum_cash_weight", 0.0))))
    masked_weights = _normalise_with_cash(masked_weights, cash_idx, float(constraints.get("cash_floor", constraints.get("minimum_cash_weight", 0.0))))
    scipy_projected = _scipy_projection(masked_weights, mask, meta, current, constraints, cash_idx)
    projected = scipy_projected if scipy_projected is not None else _iterative_projection(masked_weights, mask, meta, current, constraints, cash_idx)
    feasible = _is_feasible(projected, mask, meta, current, constraints, cash_idx)
    fallback_used = False
    if not feasible:
        fallback = np.where(mask, baseline, 0.0)
        fallback = _normalise_with_cash(fallback, cash_idx, float(constraints.get("cash_floor", constraints.get("minimum_cash_weight", 0.0))))
        fallback = _apply_turnover_cap(fallback, current, constraints)
        fallback = _normalise_with_cash(np.where(mask, fallback, 0.0), cash_idx, float(constraints.get("cash_floor", constraints.get("minimum_cash_weight", 0.0))))
        projected = fallback
        feasible = _is_feasible(projected, mask, meta, current, constraints, cash_idx)
        fallback_used = True
    adjustments = {
        "delta_bound_adjustment": float(np.abs(np.asarray(residual_action, dtype=float) - bounded).sum()),
        "eligibility_mask_adjustment": float(np.abs(raw_weights - masked_weights).sum()),
        "projection_adjustment": float(np.abs(masked_weights - projected).sum()),
        "turnover": float(np.abs(projected - current).sum()),
        "cash_weight": float(projected[cash_idx]) if cash_idx is not None else 0.0,
    }
    return ProjectionResult(raw_weights, masked_weights, projected, adjustments, bool(feasible), fallback_used)


def project_to_feasible_set(
    baseline_weights: np.ndarray,
    action: np.ndarray,
    asset_data: pd.DataFrame,
    eligibility_mask: np.ndarray,
    constraints: dict | None = None,
    cash_weight: float = 0.0,
) -> tuple[np.ndarray, pd.DataFrame]:
    """Project baseline plus bounded DRL action back into hard constraints.

    Excluded names are forced to zero. Remaining equity weights are long-only,
    unlevered and diversified using the existing optimisation constraint caps.
    """
    limits = constraints or {}
    baseline = np.asarray(baseline_weights, dtype=float)
    mask = np.asarray(eligibility_mask, dtype=bool)
    max_adjustment = float(limits.get("max_drl_adjustment", limits.get("max_adjustment", 0.015)))
    metadata = asset_data.copy().reset_index(drop=True)
    if cash_weight > 0:
        cash_row = {column: "CASH" for column in metadata.columns}
        cash_row["ticker"] = "CASH"
        cash_row["asset_class"] = "cash"
        metadata = pd.concat([metadata, pd.DataFrame([cash_row])], ignore_index=True)
        baseline_for_projection = np.concatenate([normalise_long_only(baseline) * (1 - cash_weight), [cash_weight]])
        current_for_projection = baseline_for_projection.copy()
        action_for_projection = np.concatenate([np.asarray(action, dtype=float), [0.0]])
        mask_for_projection = np.concatenate([mask, [True]])
    else:
        baseline_for_projection = normalise_long_only(baseline)
        current_for_projection = baseline_for_projection.copy()
        action_for_projection = np.asarray(action, dtype=float)
        mask_for_projection = mask
    result = project_weights(
        baseline_for_projection,
        action_for_projection,
        mask_for_projection,
        metadata,
        current_for_projection,
        limits | {"max_delta_weight": max_adjustment, "cash_floor": cash_weight},
    )
    adjusted_array = result.projected_weights[:-1] if cash_weight > 0 else result.projected_weights
    cash = float(result.projected_weights[-1]) if cash_weight > 0 else 0.0
    candidate = result.raw_weights[:-1] if cash_weight > 0 else result.raw_weights
    report = pd.DataFrame(
        {
            "ticker": asset_data.get("ticker", pd.Series(asset_data.index, index=asset_data.index)),
            "baseline_weight": baseline,
            "raw_action": np.asarray(action, dtype=float),
            "candidate_weight": candidate,
            "projected_weight": adjusted_array,
            "eligible_for_drl": mask,
            "projection_reason": np.where(mask, "bounded_and_projected", "hard_exclusion_zero_weight"),
        }
    )
    report.loc[len(report)] = {
        "ticker": "CASH",
        "baseline_weight": 0.0,
        "raw_action": 0.0,
        "candidate_weight": cash,
        "projected_weight": cash,
        "eligible_for_drl": True,
        "projection_reason": "cash_residual_unlevered",
    }
    report["feasible"] = result.feasible
    report["fallback_used"] = result.fallback_used
    for key, value in result.constraint_adjustments.items():
        report[key] = value
    return adjusted_array, report
