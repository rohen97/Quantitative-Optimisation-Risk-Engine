from src.alternative_data.alt_features import build_alt_features
from src.data_ingestion.fundamental_ingestion import load_fundamentals
from src.data_ingestion.mock_data import generate_mock_current_portfolio
from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.universe import build_universe
from src.features.feature_store import build_feature_store
from src.portfolio.portfolio_loader import load_current_portfolio
from src.regime.regime_classifier import build_regime_features


def test_feature_store_contains_portfolio_fit_features():
    universe = build_universe()
    portfolio = load_current_portfolio(mock_portfolio=generate_mock_current_portfolio(universe))
    features = build_feature_store(universe, load_prices(universe), load_fundamentals(universe), build_alt_features(universe), portfolio, build_regime_features(universe))
    assert "incremental_portfolio_cvar" in features.columns
    assert "diversification_benefit_score" in features.columns
    assert len(features) == len(universe)
