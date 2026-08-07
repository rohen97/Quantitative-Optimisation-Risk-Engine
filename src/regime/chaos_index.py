from __future__ import annotations

import numpy as np
import pandas as pd


def _robust_return_matrix(returns: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Winsorise cross-sectional data errors before systemic-risk aggregation."""
    values = returns.to_numpy(dtype=float, copy=True)
    invalid = ~np.isfinite(values)
    values[invalid] = 0.0
    fixed_outliers = np.abs(values) > 1.0
    np.clip(values, -1.0, 1.0, out=values)
    if values.shape[1] >= 20:
        lower = np.quantile(values, 0.005, axis=1)
        upper = np.quantile(values, 0.995, axis=1)
        values = np.minimum(np.maximum(values, lower[:, None]), upper[:, None])
    adjusted_fraction = float((invalid | fixed_outliers).mean())
    return pd.DataFrame(values, index=returns.index, columns=returns.columns), adjusted_fraction


def _correlation_metrics(returns: pd.DataFrame) -> tuple[float, float, float]:
    """Calculate correlation statistics through the smaller time-domain matrix."""
    values = returns.to_numpy(dtype=float, copy=True)
    observations, assets = values.shape
    if assets <= 1 or observations <= 1:
        return 0.0, 1.0, 1.0
    centred = values - values.mean(axis=0, keepdims=True)
    norms = np.linalg.norm(centred, axis=0)
    valid = norms > 1e-14
    standardised = np.zeros_like(centred)
    standardised[:, valid] = centred[:, valid] / norms[valid]
    valid_assets = int(valid.sum())
    summed = standardised.sum(axis=1)
    off_diagonal_sum = float(summed @ summed - valid_assets)
    average_correlation = off_diagonal_sum / (assets * (assets - 1))
    eigenvalues = np.linalg.eigvalsh(standardised @ standardised.T)
    eigenvalues = np.clip(eigenvalues, 0.0, None)
    largest_eigen = float(eigenvalues.max()) if len(eigenvalues) else 1.0
    squared_sum = float(np.square(eigenvalues).sum())
    effective_bets = float(eigenvalues.sum() ** 2 / squared_sum) if squared_sum else 1.0
    return average_correlation, largest_eigen, effective_bets


def _rolling_correlation_instability(returns: pd.DataFrame, window: int = 21) -> float:
    """Calculate rolling correlation instability without N by N matrices."""
    values = returns.to_numpy(dtype=float, copy=False)
    if len(values) <= window or values.shape[1] <= 1:
        return 0.0

    window_count = len(values) - window + 1
    asset_count = values.shape[1]
    chunk_size = min(2048, asset_count)
    row_sums = np.zeros((window_count, window), dtype=float)
    valid_counts = np.zeros(window_count, dtype=np.int64)

    def standardised_windows(start: int, end: int) -> tuple[np.ndarray, np.ndarray]:
        asset_windows = np.lib.stride_tricks.sliding_window_view(
            values[:, start:end],
            window_shape=window,
            axis=0,
        )
        centred = asset_windows - asset_windows.mean(axis=2, keepdims=True)
        norms = np.linalg.norm(centred, axis=2)
        valid = norms > 1e-14
        standardised = np.divide(
            centred,
            norms[:, :, None],
            out=np.zeros_like(centred),
            where=valid[:, :, None],
        )
        return standardised, valid

    for start in range(0, asset_count, chunk_size):
        standardised, valid = standardised_windows(start, min(start + chunk_size, asset_count))
        row_sums += standardised.sum(axis=1)
        valid_counts += valid.sum(axis=1)
    if int((valid_counts > 0).sum()) <= 1:
        return 0.0

    instability_sum = 0.0
    finite_assets = 0
    for start in range(0, asset_count, chunk_size):
        standardised, valid = standardised_windows(start, min(start + chunk_size, asset_count))
        column_means = np.einsum("wcl,wl->wc", standardised, row_sums, optimize=True)
        column_means = np.divide(
            column_means,
            valid_counts[:, None],
            out=np.full_like(column_means, np.nan),
            where=valid & (valid_counts[:, None] > 0),
        )
        with np.errstate(invalid="ignore", divide="ignore"):
            instability = np.nanstd(column_means, axis=0, ddof=1)
        finite = np.isfinite(instability)
        instability_sum += float(instability[finite].sum())
        finite_assets += int(finite.sum())
    return instability_sum / finite_assets if finite_assets else 0.0


def calculate_wolf_chaos_index_from_returns(returns: pd.DataFrame) -> pd.DataFrame:
    """Calculate FCIX-lite metrics from a date-by-ticker return matrix."""
    returns = returns.sort_index().tail(126).fillna(0)
    if returns.empty:
        raise ValueError("Wolf Chaos Index requires at least one return observation.")
    returns, adjusted_fraction = _robust_return_matrix(returns)
    dispersion = float(returns.std(axis=1).mean())
    avg_corr, largest_eigen, effective_bets = _correlation_metrics(returns)
    corr_instability = _rolling_correlation_instability(returns) if len(returns) > 30 else 0.0
    breadth = float((returns.iloc[-21:] > 0).mean(axis=1).mean())
    vol_of_vol = float(returns.std(axis=1).rolling(21).std().mean())
    drawdown_breadth = float((returns.tail(63).cumsum() < 0).mean(axis=1).mean())
    raw = (
        dispersion * 800
        + max(avg_corr, 0) * 25
        + corr_instability * 40
        + largest_eigen / max(returns.shape[1], 1) * 25
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
                "adjusted_return_fraction": adjusted_fraction,
                "wolf_chaos_index": index,
            }
        ]
    )


def calculate_wolf_chaos_index(prices: pd.DataFrame) -> pd.DataFrame:
    """Calculate FCIX-lite systemic stress metrics from long-form prices."""
    returns = prices.pivot(index="date", columns="ticker", values="return")
    return calculate_wolf_chaos_index_from_returns(returns)
