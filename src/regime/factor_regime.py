from __future__ import annotations

import numpy as np
import pandas as pd

from src.regime.mock_regime_data import FACTOR_COLUMNS

REGIME_LABELS = ["crisis", "steady_state", "inflation", "walking_on_ice"]


def _fallback_probabilities(latest: pd.Series) -> dict[str, float]:
    stress = max(0.0, float(latest.get("credit_proxy", 0) + latest.get("europe_recession_proxy", 0))) / 4
    inflation = max(0.0, float(latest.get("inflation_proxy", 0) + latest.get("rates_proxy", 0))) / 4
    momentum = max(0.0, float(latest.get("momentum_factor", 0))) / 4
    crisis = np.clip(0.20 + stress, 0.05, 0.70)
    inflation_p = np.clip(0.15 + inflation, 0.05, 0.65)
    walking = np.clip(0.20 + momentum * 0.5 + stress * 0.4, 0.05, 0.60)
    steady = max(0.05, 1 - crisis - inflation_p - walking)
    probs = np.array([crisis, steady, inflation_p, walking], dtype=float)
    probs = probs / probs.sum()
    return dict(zip(REGIME_LABELS, probs))


def fit_gmm_regime_model(factor_features: pd.DataFrame, n_clusters: int = 4):
    """Fit a Gaussian Mixture regime model when sklearn and data are available."""
    try:
        from sklearn.mixture import GaussianMixture
    except Exception:
        return None
    if len(factor_features) < n_clusters * 5:
        return None
    model = GaussianMixture(n_components=n_clusters, random_state=42)
    model.fit(factor_features[FACTOR_COLUMNS])
    return model


def predict_factor_regime_probabilities(factor_features: pd.DataFrame, model=None) -> pd.DataFrame:
    """Predict factor-regime probabilities for the latest Global factor observation."""
    latest = factor_features[factor_features["region"].eq("Global")].sort_values("date").iloc[-1]
    if model is not None:
        raw = model.predict_proba(latest[FACTOR_COLUMNS].to_frame().T)[0]
        order = np.argsort(model.means_.mean(axis=1))
        probs = np.zeros(4)
        for label_idx, cluster_idx in enumerate(order[:4]):
            probs[label_idx] = raw[cluster_idx]
        if probs.sum() == 0:
            probs = raw[:4]
        probs = probs / probs.sum()
        probabilities = dict(zip(REGIME_LABELS, probs))
    else:
        probabilities = _fallback_probabilities(latest)
    dominant = max(probabilities, key=probabilities.get)
    return pd.DataFrame(
        [
            {
                "as_of_date": latest["date"],
                "crisis_probability": probabilities["crisis"],
                "steady_state_probability": probabilities["steady_state"],
                "inflation_probability": probabilities["inflation"],
                "walking_on_ice_probability": probabilities["walking_on_ice"],
                "dominant_factor_regime": dominant,
                "factor_regime_confidence": probabilities[dominant],
            }
        ]
    )
