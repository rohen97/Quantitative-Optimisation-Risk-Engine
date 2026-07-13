from src.alternative_data.alt_features import build_alt_features
from src.data_ingestion.fundamental_ingestion import load_fundamentals
from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.universe import build_universe
from src.features.feature_store import build_feature_store
from src.portfolio.portfolio_loader import load_current_portfolio
from src.regime.regime_classifier import build_regime_features


def test_feature_store_contains_portfolio_fit_features():
    universe = build_universe()
    portfolio = load_current_portfolio("data/external/current_portfolio_template.csv")
    features = build_feature_store(universe, load_prices(universe), load_fundamentals(universe), build_alt_features(universe), portfolio, build_regime_features(universe))
    assert "incremental_portfolio_cvar" in features.columns
    assert "diversification_benefit_score" in features.columns
    assert len(features) == len(universe)


def test_feature_store_core_calculations_and_score_ranges():
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
    required = [
        "trailing_12m_dps",
        "dividend_growth_3y",
        "fcf_dividend_cover",
        "free_cash_flow",
        "operating_cash_flow",
        "capex",
        "net_debt",
        "debt_to_equity",
        "enterprise_value",
        "fcf_yield",
        "annualised_volatility",
        "var_5",
        "cvar_5",
        "average_daily_value_usd",
        "days_to_liquidate_1pct_nav",
    ]
    for column in required:
        assert column in features.columns
    assert (features["fcf_yield"].notna()).all()
    for score in [
        "dividend_safety_score",
        "cash_flow_quality_score",
        "balance_sheet_strength_score",
        "valuation_score",
        "risk_score",
        "liquidity_score",
    ]:
        assert features[score].between(0, 100).all()
