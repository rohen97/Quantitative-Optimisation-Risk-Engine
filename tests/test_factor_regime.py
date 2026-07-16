from src.regime.factor_lens import calculate_factor_returns, standardise_factor_features
from src.regime.factor_regime import predict_factor_regime_probabilities


def test_factor_regime_probabilities_sum_to_one():
    factor_features = standardise_factor_features(calculate_factor_returns())
    probabilities = predict_factor_regime_probabilities(factor_features, model=None)
    probability_columns = [
        "crisis_probability",
        "steady_state_probability",
        "inflation_probability",
        "walking_on_ice_probability",
    ]
    assert abs(float(probabilities[probability_columns].sum(axis=1).iloc[0]) - 1) < 1e-9
    assert probabilities["dominant_factor_regime"].iloc[0] in {"crisis", "steady_state", "inflation", "walking_on_ice"}
