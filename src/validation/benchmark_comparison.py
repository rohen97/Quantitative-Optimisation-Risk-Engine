from __future__ import annotations

import numpy as np
import pandas as pd

from src.validation.portfolio_backtesting import calculate_portfolio_performance
from src.validation.statistics.bootstrap import block_bootstrap_interval


def compare_benchmarks(returns: pd.DataFrame, block_size: int = 20, samples: int = 1000, seed: int = 42) -> pd.DataFrame:
    rows = []
    for strategy in returns.columns:
        series = returns[strategy]
        metrics = calculate_portfolio_performance(series)
        lower, upper = block_bootstrap_interval(series.to_numpy(), samples=samples, block_size=block_size, seed=seed)
        rows.append({"strategy": strategy, **metrics.__dict__, "mean_return_ci_lower": lower, "mean_return_ci_upper": upper})
    return pd.DataFrame(rows)


def pairwise_return_differences(returns: pd.DataFrame, baseline: str) -> pd.DataFrame:
    if baseline not in returns:
        raise ValueError(f"Missing baseline: {baseline}")
    rows = []
    for strategy in returns.columns:
        if strategy == baseline:
            continue
        difference = returns[strategy] - returns[baseline]
        rows.append({"strategy": strategy, "baseline": baseline, "mean_return_difference": float(np.mean(difference)), "observations": int(difference.notna().sum())})
    return pd.DataFrame(rows)
