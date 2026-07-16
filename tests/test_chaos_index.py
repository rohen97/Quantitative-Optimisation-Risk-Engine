from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.universe import build_universe
from src.regime.chaos_index import calculate_wolf_chaos_index
from src.regime.chaos_regime import classify_chaos_regime


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
