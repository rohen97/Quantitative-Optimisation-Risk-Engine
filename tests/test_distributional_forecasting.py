from src.data_ingestion.fundamental_ingestion import load_fundamentals
from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.universe import build_universe
from src.features.feature_store import build_feature_store
from src.models.distributional_forecasting import build_distributional_forecasts
from src.models.forecasting import build_ml_forecast_features
from src.models.research_extensions import list_research_extension_points
from src.portfolio.portfolio_loader import load_current_portfolio
from src.regime.regime_classifier import build_regime_features


def _features():
    universe = build_universe(n=8)
    prices = load_prices(universe)
    fundamentals = load_fundamentals(universe)
    sentiment = universe[["security_id", "ticker"]].copy()
    portfolio = load_current_portfolio("data/external/current_portfolio_template.csv")
    features = build_feature_store(universe, prices, fundamentals, sentiment, portfolio, build_regime_features(universe))
    return features


def test_distributional_forecaster_outputs_parameters_and_risk_metrics():
    features = _features()
    base = build_ml_forecast_features(features)["ml_features"]
    distributional = build_distributional_forecasts(features, base)
    assert {"distribution_mu_12m", "distribution_sigma_12m", "distribution_nu_12m", "distribution_xi_12m"}.issubset(distributional.columns)
    assert (distributional["distribution_sigma_12m"] > 0).all()
    assert (distributional["distribution_nu_12m"] > 2).all()
    assert (distributional["distribution_xi_12m"] > 0).all()
    assert (distributional["p5_return_12m"] <= distributional["p50_return_12m"]).all()
    assert (distributional["p50_return_12m"] <= distributional["p95_return_12m"]).all()
    assert (distributional["var_1_12m"] <= distributional["var_5_12m"]).all()
    assert (distributional["cvar_5_12m"] <= distributional["var_5_12m"]).all()
    assert (distributional["expected_shortfall_5_12m"] <= distributional["var_5_12m"]).all()
    assert distributional["tail_risk_score"].between(0, 100).all()
    assert distributional["skewness_risk_score"].between(0, 100).all()


def test_future_architecture_placeholders_include_transformer_and_xlstm():
    extensions = list_research_extension_points()
    deep = extensions[extensions["extension_area"].eq("deep_architectures")].iloc[0]
    assert "transformer_encoder" in deep["supported_values"]
    assert "xlstm" in deep["supported_values"]
