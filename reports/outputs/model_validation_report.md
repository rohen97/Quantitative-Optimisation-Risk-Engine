# Model Validation Report

## Model Summary
Deterministic mock ML Forecasting & Return Distribution Engine for conservative equity selection.
The distribution layer is inspired by probabilistic return forecasting research that predicts distribution parameters rather than only point returns.

## Data Mode
mock / dry-run. No real APIs, paid data, OpenAI or Claude calls are used.

## Feature Groups Used
- quality_features: cash_flow_quality_score, balance_sheet_strength_score, dividend_safety_score, roe, roic
- income_features: dividend_yield, payout_ratio, fcf_dividend_cover, free_cash_flow_yield
- valuation_features: valuation_score, pe_ratio, pb_ratio
- risk_features: volatility_1y, beta_local_market, max_drawdown_1y, var_5, cvar_5
- liquidity_features: liquidity_score, liquidity_stress_score, average_daily_value_usd
- sentiment_features: sentiment_alt_signal_score, negative_news_intensity, credit_stress_score, regulatory_risk_score
- narrative_features: risk_reframing_score, distress_similarity_score, dividend_risk_similarity_score
- regime_features: regime_suitability_score, regime_risk_score, regime_deterioration_probability
- portfolio_fit_features: diversification_benefit_score, incremental_portfolio_cvar, portfolio_fit_score
- categorical_features: region, country, sector, currency, dominant_regime

## Targets Used
Forward total return, price return, dividend return, volatility, max drawdown, dividend-cut event and large-drawdown event for 3M, 6M, 9M and 12M horizons.

## Validation Method
Walk-forward-ready chronological validation interfaces. No random train-test split is used. The report includes proxy placeholders for probabilistic metrics such as Log Predictive Score, CRPS, PIT calibration and VaR exceedance rates.

## Metrics By Horizon
- 3M: `{"bottom_decile_forward_return": 0.0, "calibration_error": 0.026962675164763143, "crps_proxy": 0.0594062716016991, "directional_accuracy": 0.0, "hit_ratio": 0.0, "log_predictive_score_proxy": 0.057367558516808324, "mae": 0.0594062716016991, "pit_uniformity_proxy": 0.5, "quantile_coverage": 0.9, "r2": -6013839060.663119, "rank_ic": 0.0, "rmse": 0.06547071220451728, "spearman_rank_correlation": 0.0, "top_decile_forward_return": 0.0, "var_5_exceedance_rate_proxy": 0.0}`
- 6M: `{"bottom_decile_forward_return": 0.0, "calibration_error": 0.053925350329526285, "crps_proxy": 0.1188125432033982, "directional_accuracy": 0.0, "hit_ratio": 0.0, "log_predictive_score_proxy": 0.11103123852720959, "mae": 0.1188125432033982, "pit_uniformity_proxy": 0.5, "quantile_coverage": 0.9, "r2": -24055356245.652477, "rank_ic": 0.0, "rmse": 0.13094142440903456, "spearman_rank_correlation": 0.0, "top_decile_forward_return": 0.0, "var_5_exceedance_rate_proxy": 0.0}`
- 9M: `{"bottom_decile_forward_return": 0.0, "calibration_error": 0.08088802549428943, "crps_proxy": 0.1782188148050973, "directional_accuracy": 0.0, "hit_ratio": 0.0, "log_predictive_score_proxy": 0.16146762565797873, "mae": 0.1782188148050973, "pit_uniformity_proxy": 0.5, "quantile_coverage": 0.9, "r2": -54124551553.96808, "rank_ic": 0.0, "rmse": 0.19641213661355186, "spearman_rank_correlation": 0.0, "top_decile_forward_return": 0.0, "var_5_exceedance_rate_proxy": 0.0}`
- 12M: `{"bottom_decile_forward_return": 0.0, "calibration_error": 0.1078160606020319, "crps_proxy": 0.23759472290002523, "directional_accuracy": 0.0, "hit_ratio": 0.0, "log_predictive_score_proxy": 0.20903898973806365, "mae": 0.23759472290002523, "pit_uniformity_proxy": 0.5, "quantile_coverage": 0.9, "r2": -96203503850.28937, "rank_ic": 0.0, "rmse": 0.2618584599851225, "spearman_rank_correlation": 0.0, "top_decile_forward_return": 0.0, "var_5_exceedance_rate_proxy": 0.0}`

## Leakage Controls
- Forecast feature matrix drops all `forward_*` target columns.
- Target generation uses future windows only for labels, not features.
- Walk-forward split preserves time ordering and supports embargo periods.
- Filing-date awareness is reserved for future real fundamental history.

## Known Limitations
- Current engine uses deterministic mock/fallback models, not trained production models.
- The current skewed Student-t distribution parameters are rule-based proxies, not neural-network outputs optimized by negative log likelihood.
- No real vendor history, corporate action feed or full point-in-time fundamentals are connected.
- Quantile bands use volatility and uncertainty fallbacks rather than conformal prediction.

## Next Improvements
Add real historical data, CNN/LSTM distributional models, negative-log-likelihood training for Normal/Student-t/skewed-Student-t parameters, purged cross-validation, conformal prediction, XGBoost/LightGBM, Bayesian models, richer dividend-risk classifiers and MLflow registry integration.
