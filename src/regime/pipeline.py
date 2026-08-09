from __future__ import annotations

import pandas as pd

from src.regime.chaos_index import calculate_wolf_chaos_index
from src.regime.chaos_regime import classify_chaos_regime
from src.regime.factor_lens import calculate_factor_returns, standardise_factor_features
from src.regime.factor_regime import fit_gmm_regime_model, predict_factor_regime_probabilities
from src.regime.informational_drivers import run_informational_driver_model
from src.regime.regime_fusion import fuse_regime_signals
from src.regime.regime_suitability import build_regime_suitability_scores
from src.regime.regime_transitions import build_regime_transition_matrix


def run_regime_pipeline(
    universe: pd.DataFrame,
    prices: pd.DataFrame,
    features: pd.DataFrame,
    alt_features: pd.DataFrame | None = None,
    narrative_features: pd.DataFrame | None = None,
    regime_config: dict | None = None,
    chaos_index: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    """Run factor, chaos, informational, fusion, transition and suitability engines."""
    config = (regime_config or {}).get("regime", regime_config or {})
    factor_lens = calculate_factor_returns()
    factor_features = standardise_factor_features(factor_lens)
    model = fit_gmm_regime_model(factor_features, config.get("factor_regime", {}).get("n_clusters", 4))
    factor_probs = predict_factor_regime_probabilities(factor_features, model)
    chaos_index = chaos_index.copy() if chaos_index is not None else calculate_wolf_chaos_index(prices)
    thresholds = config.get("chaos_regime", {}).get("thresholds", {})
    chaos_probs = classify_chaos_regime(
        chaos_index,
        low_max=thresholds.get("low_chaos_max", 35),
        intermediate_max=thresholds.get("intermediate_chaos_max", 70),
    )
    drivers = run_informational_driver_model(alt_features, narrative_features)
    dashboard = fuse_regime_signals(factor_probs, chaos_probs, drivers)
    transitions = build_regime_transition_matrix(factor_lens, factor_probs, chaos_probs, dashboard.iloc[0]["dominant_regime"])
    suitability = build_regime_suitability_scores(
        universe,
        features,
        dashboard,
        neutral_score=config.get("suitability", {}).get("neutral_score", 50),
    )
    regime_features = dashboard.copy()
    return {
        "regime_features": regime_features,
        "factor_regime_probabilities": factor_probs,
        "chaos_regime_probabilities": chaos_probs,
        "informational_driver_model": drivers,
        "regime_transition_matrix": transitions,
        "regime_dashboard_summary": dashboard,
        "regime_suitability_scores": suitability,
    }
