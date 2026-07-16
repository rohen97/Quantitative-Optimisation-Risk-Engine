from __future__ import annotations

import pandas as pd

from src.models.forecast_features import build_forecast_feature_matrix
from src.models.forecast_validation import build_model_validation_report
from src.models.forecasting import build_ml_forecast_features
from src.models.model_registry import build_model_registry
from src.models.probabilistic_metrics import build_probabilistic_validation
from src.models.research_extensions import (
    build_distribution_trading_research_signals,
    list_research_extension_points,
    run_distribution_sensitivity_analysis,
)
from src.models.targets import HORIZONS_MONTHS, build_forward_return_targets
from src.models.var_es_backtesting import build_var_es_backtest_report
from src.models.walk_forward import calculate_validation_metrics


def run_ml_forecasting_engine(
    features: pd.DataFrame,
    prices: pd.DataFrame,
    regime_dashboard: pd.DataFrame | None = None,
    ml_config: dict | None = None,
) -> dict[str, pd.DataFrame | str]:
    """Run mock ML forecasting, distribution, risk, validation and registry outputs."""
    config = (ml_config or {}).get("ml_forecasting", ml_config or {})
    horizons = config.get("horizons_months", HORIZONS_MONTHS)
    targets = build_forward_return_targets(prices, features)
    outputs = build_ml_forecast_features(features, regime_dashboard)
    _, _, feature_groups = build_forecast_feature_matrix(features)
    metrics_by_horizon: dict[int, dict[str, float]] = {}
    latest_forecasts = outputs["ml_features"]
    latest_targets = targets.sort_values("date").groupby("ticker").tail(1)
    for horizon in horizons:
        target_col = f"forward_total_return_{horizon}m"
        forecast_col = f"expected_total_return_{horizon}m"
        latest_target = latest_targets[["ticker", target_col]].merge(
            latest_forecasts[["ticker", forecast_col]], on="ticker", how="inner"
        )
        metrics_by_horizon[int(horizon)] = calculate_validation_metrics(latest_target[target_col].fillna(0), latest_target[forecast_col].fillna(0))
    realized_12m = latest_targets[["ticker", "forward_total_return_12m"]].merge(latest_forecasts, on="ticker", how="inner")
    outputs["model_registry"] = build_model_registry(metrics_by_horizon)
    outputs["probabilistic_validation"] = build_probabilistic_validation(realized_12m["forward_total_return_12m"], realized_12m, horizon=12)
    outputs["var_es_backtest_report"] = build_var_es_backtest_report(realized_12m["forward_total_return_12m"], realized_12m, horizon=12)
    outputs["distribution_sensitivity_analysis"] = run_distribution_sensitivity_analysis(latest_forecasts)
    outputs["distribution_trading_research_signals"] = build_distribution_trading_research_signals(latest_forecasts)
    outputs["distribution_research_extension_points"] = list_research_extension_points()
    outputs["model_validation_report"] = build_model_validation_report(metrics_by_horizon, feature_groups)
    outputs["ml_targets"] = targets
    return outputs
