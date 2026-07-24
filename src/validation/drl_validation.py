from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DRLApprovalDecision:
    status: str
    accepted_blend: float
    reasons: tuple[str, ...]


def evaluate_drl_approval(
    classical_net_sharpe: float,
    drl_net_sharpe: float,
    classical_max_drawdown: float,
    drl_max_drawdown: float,
    classical_expected_shortfall: float,
    drl_expected_shortfall: float,
    seed_sharpe_std: float,
    constraint_passed: bool,
    maximum_seed_sharpe_std: float,
    maximum_blend: float,
) -> DRLApprovalDecision:
    reasons = []
    if not constraint_passed:
        reasons.append("Projected DRL portfolio failed constraints.")
    if drl_net_sharpe <= classical_net_sharpe:
        reasons.append("DRL did not improve net Sharpe.")
    if drl_max_drawdown < classical_max_drawdown:
        reasons.append("DRL worsened maximum drawdown.")
    if drl_expected_shortfall > classical_expected_shortfall:
        reasons.append("DRL worsened Expected Shortfall.")
    if seed_sharpe_std > maximum_seed_sharpe_std:
        reasons.append("DRL results were unstable across seeds.")
    if reasons:
        return DRLApprovalDecision("rejected", 0.0, tuple(reasons))
    return DRLApprovalDecision("conditionally_accepted", min(maximum_blend, 0.25), ("DRL passed risk, stability and constraint requirements.",))


def validate_seed_stability(seed_results: pd.DataFrame, minimum_seeds: int = 5, maximum_sharpe_std: float = 0.35, maximum_return_std: float = 0.10) -> pd.DataFrame:
    seeds = seed_results[seed_results.get("row_type", "seed").astype(str).eq("seed")] if not seed_results.empty and "row_type" in seed_results else seed_results
    seed_count = int(seeds.get("seed", pd.Series(dtype=float)).nunique())
    sharpe_std = float(pd.to_numeric(seeds.get("sharpe", pd.Series(dtype=float)), errors="coerce").std(ddof=0)) if not seeds.empty else float("nan")
    return_std = float(pd.to_numeric(seeds.get("total_net_return", pd.Series(dtype=float)), errors="coerce").std(ddof=0)) if not seeds.empty else float("nan")
    passed = seed_count >= minimum_seeds and np.isfinite(sharpe_std) and sharpe_std <= maximum_sharpe_std and np.isfinite(return_std) and return_std <= maximum_return_std
    return pd.DataFrame([{"seed_count": seed_count, "sharpe_std": sharpe_std, "return_std": return_std, "status": "PASS" if passed else "FAIL"}])
