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
- 3M: `{"bottom_decile_forward_return": 0.0, "calibration_error": 0.026583043660799645, "crps_proxy": 0.05919144186263384, "directional_accuracy": 0.0, "hit_ratio": 0.0, "log_predictive_score_proxy": 0.05716840427089123, "mae": 0.05919144186263384, "pit_uniformity_proxy": 0.5, "quantile_coverage": 0.9, "r2": -5962176497.359688, "rank_ic": 0.0, "rmse": 0.06521213325815728, "spearman_rank_correlation": 0.0, "top_decile_forward_return": 0.0, "var_5_exceedance_rate_proxy": 0.0}`
- 6M: `{"bottom_decile_forward_return": 0.0, "calibration_error": 0.05316608732159929, "crps_proxy": 0.11838288372526767, "directional_accuracy": 0.0, "hit_ratio": 0.0, "log_predictive_score_proxy": 0.11066004866462248, "mae": 0.11838288372526767, "pit_uniformity_proxy": 0.5, "quantile_coverage": 0.9, "r2": -23848705992.43875, "rank_ic": 0.0, "rmse": 0.13042426651631456, "spearman_rank_correlation": 0.0, "top_decile_forward_return": 0.0, "var_5_exceedance_rate_proxy": 0.0}`
- 9M: `{"bottom_decile_forward_return": 0.0, "calibration_error": 0.07974913098239893, "crps_proxy": 0.1775743255879015, "directional_accuracy": 0.0, "hit_ratio": 0.0, "log_predictive_score_proxy": 0.1609463585139783, "mae": 0.1775743255879015, "pit_uniformity_proxy": 0.5, "quantile_coverage": 0.9, "r2": -53659588484.23719, "rank_ic": 0.0, "rmse": 0.19563639977447186, "spearman_rank_correlation": 0.0, "top_decile_forward_return": 0.0, "var_5_exceedance_rate_proxy": 0.0}`
- 12M: `{"bottom_decile_forward_return": 0.0, "calibration_error": 0.10629750987857661, "crps_proxy": 0.23673538228648403, "directional_accuracy": 0.0, "hit_ratio": 0.0, "log_predictive_score_proxy": 0.2083856216684902, "mae": 0.23673538228648403, "pit_uniformity_proxy": 0.5, "quantile_coverage": 0.9, "r2": -95376965963.76413, "rank_ic": 0.0, "rmse": 0.26082411633326785, "spearman_rank_correlation": 0.0, "top_decile_forward_return": 0.0, "var_5_exceedance_rate_proxy": 0.0}`

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
