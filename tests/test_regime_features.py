from src.data_ingestion.universe import build_universe
from src.regime.factor_lens import calculate_factor_returns, standardise_factor_features


def test_factor_lens_contains_active_regions_and_no_india():
    factors = calculate_factor_returns()
    assert {"Global", "DACH", "EU ex-DACH", "UK", "Mainland China", "Hong Kong"}.issubset(set(factors["region"]))
    assert "India" not in set(factors["region"])


def test_standardised_factor_features_are_complete():
    factors = calculate_factor_returns()
    features = standardise_factor_features(factors)
    assert features.shape[0] == factors.shape[0]
    assert features.drop(columns=["date", "region"]).notna().all().all()


def test_universe_keeps_india_removed():
    universe = build_universe()
    assert "India" not in set(universe["region"])
