import numpy as np
import pandas as pd

from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.universe import build_universe
from src.regime.chaos_index import _rolling_correlation_instability, calculate_wolf_chaos_index
from src.regime.chaos_regime import classify_chaos_regime


def _reference_rolling_instability(returns: pd.DataFrame, window: int) -> float:
    values = returns.to_numpy(dtype=float, copy=False)
    rolling_means = []
    for end in range(window, len(values) + 1):
        sample = values[end - window : end]
        centred = sample - sample.mean(axis=0, keepdims=True)
        norms = np.linalg.norm(centred, axis=0)
        valid = norms > 1e-14
        if not valid.any():
            continue
        standardised = np.zeros_like(centred)
        standardised[:, valid] = centred[:, valid] / norms[valid]
        column_means = np.full(values.shape[1], np.nan)
        row_sum = standardised[:, valid].sum(axis=1)
        column_means[valid] = standardised[:, valid].T @ row_sum / int(valid.sum())
        rolling_means.append(column_means)
    if len(rolling_means) <= 1:
        return 0.0
    return float(np.nanmean(np.nanstd(np.vstack(rolling_means), axis=0, ddof=1)))


def test_wolf_chaos_index_is_bounded():
    prices = load_prices(build_universe())
    chaos = calculate_wolf_chaos_index(prices)
    assert chaos["wolf_chaos_index"].between(0, 100).all()
    assert chaos["effective_number_of_bets"].iloc[0] > 0


def test_chaos_regime_probabilities_sum_to_one():
    prices = load_prices(build_universe())
    chaos = calculate_wolf_chaos_index(prices)
    probabilities = classify_chaos_regime(chaos)
    probability_columns = ["low_chaos_probability", "intermediate_chaos_probability", "high_chaos_probability"]
    assert abs(float(probabilities[probability_columns].sum(axis=1).iloc[0]) - 1) < 1e-9
    assert probabilities["dominant_chaos_regime"].iloc[0] in {"low_chaos", "intermediate_chaos", "high_chaos"}


def test_chunked_rolling_instability_matches_reference_calculation():
    rng = np.random.default_rng(17)
    returns = pd.DataFrame(rng.normal(0, 0.02, size=(39, 23)))
    returns[22] = 0.0

    actual = _rolling_correlation_instability(returns, window=9)
    expected = _reference_rolling_instability(returns, window=9)

    assert np.isclose(actual, expected, rtol=1e-12, atol=1e-12)
