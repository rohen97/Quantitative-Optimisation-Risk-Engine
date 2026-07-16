from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_wolf_chaos_index(prices: pd.DataFrame) -> pd.DataFrame:
    """Calculate FCIX-lite systemic stress metrics and Wolf Chaos Index."""
    returns = prices.pivot(index="date", columns="ticker", values="return").tail(126).fillna(0)
    dispersion = float(returns.std(axis=1).mean())
    corr = returns.corr().fillna(0)
    avg_corr = float(corr.where(~np.eye(len(corr), dtype=bool)).stack().mean()) if len(corr) > 1 else 0.0
    corr_instability = float(returns.rolling(21).corr().groupby(level=0).mean().std().mean()) if len(returns) > 30 else 0.0
    eigenvalues = np.linalg.eigvalsh(corr.to_numpy()) if len(corr) else np.array([1])
    largest_eigen = float(eigenvalues.max())
    effective_bets = float((eigenvalues.sum() ** 2) / np.square(eigenvalues).sum()) if np.square(eigenvalues).sum() else 1.0
    breadth = float((returns.iloc[-21:] > 0).mean(axis=1).mean())
    vol_of_vol = float(returns.std(axis=1).rolling(21).std().mean())
    drawdown_breadth = float((returns.tail(63).cumsum() < 0).mean(axis=1).mean())
    raw = (
        dispersion * 800
        + max(avg_corr, 0) * 25
        + corr_instability * 40
        + largest_eigen / max(len(corr), 1) * 25
        + (1 / max(effective_bets, 1)) * 20
        + (1 - breadth) * 15
        + vol_of_vol * 500
        + drawdown_breadth * 20
    )
    index = float(np.clip(raw, 0, 100))
    return pd.DataFrame(
        [
            {
                "as_of_date": returns.index.max(),
                "cross_sectional_return_dispersion": dispersion,
                "average_pairwise_correlation": avg_corr,
                "correlation_instability": corr_instability,
                "largest_correlation_eigenvalue": largest_eigen,
                "effective_number_of_bets": effective_bets,
                "market_breadth": breadth,
                "volatility_of_volatility": vol_of_vol,
                "drawdown_breadth": drawdown_breadth,
                "wolf_chaos_index": index,
            }
        ]
    )
