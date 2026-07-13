from src.alternative_data.alt_features import build_alt_features
from src.data_ingestion.fundamental_ingestion import load_fundamentals
from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.universe import build_universe
from src.features.feature_store import build_feature_store
from src.portfolio.portfolio_loader import load_current_portfolio
from src.regime.regime_classifier import build_regime_features


def test_portfolio_fit_score_range_and_columns():
    universe = build_universe()
    portfolio = load_current_portfolio("data/external/current_portfolio_template.csv")
    features = build_feature_store(
        universe,
        load_prices(universe),
        load_fundamentals(universe),
        build_alt_features(universe),
        portfolio,
        build_regime_features(universe),
    )
    expected = [
        "correlation_with_current_portfolio",
        "incremental_sector_exposure",
        "incremental_country_exposure",
        "incremental_region_exposure",
        "incremental_currency_exposure",
        "incremental_dividend_income",
        "concentration_impact_score",
        "diversification_benefit_score",
        "portfolio_fit_score",
    ]
    for column in expected:
        assert column in features.columns
    assert features["portfolio_fit_score"].between(0, 100).all()
