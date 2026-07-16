from src.data_ingestion.fundamental_ingestion import load_fundamentals
from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.universe import build_universe
from src.features.feature_store import build_feature_store
from src.models.targets import HORIZONS_MONTHS, build_forward_return_targets
from src.portfolio.portfolio_loader import load_current_portfolio
from src.regime.regime_classifier import build_regime_features


def test_forward_target_columns_are_generated():
    universe = build_universe(n=4)
    prices = load_prices(universe)
    fundamentals = load_fundamentals(universe)
    sentiment = universe[["security_id", "ticker"]].copy()
    portfolio = load_current_portfolio("data/external/current_portfolio_template.csv")
    features = build_feature_store(universe, prices, fundamentals, sentiment, portfolio, build_regime_features(universe))
    targets = build_forward_return_targets(prices, features)
    for horizon in HORIZONS_MONTHS:
        assert f"forward_total_return_{horizon}m" in targets.columns
        assert f"forward_price_return_{horizon}m" in targets.columns
        assert f"forward_dividend_return_{horizon}m" in targets.columns
        assert f"forward_volatility_{horizon}m" in targets.columns
        assert f"forward_max_drawdown_{horizon}m" in targets.columns
    assert "dividend_cut_event_forward_12m" in targets.columns
    assert "large_drawdown_event_forward_12m" in targets.columns
