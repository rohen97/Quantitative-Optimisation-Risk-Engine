# The Wolf Quant Model

Portfolio-aware, regime-aware and sentiment-aware conservative listed-equity selection MVP for DACH, EU ex-DACH, UK, Mainland China and Hong Kong.

The active stock-selection universe is listed equities only. India has been removed from the active universe; options and ETFs are not included unless explicitly configured later.

The pipeline now compares three recommendation branches:

- Portfolio-Aware Quant Model
- Clean-Sheet Quant Model
- OpenAI / Claude Analyst Benchmark Model in mock mode

The LLM benchmark is an explanation and comparison layer only. It cannot bypass hard quant risk controls.

Run the mock-data pipeline:

```bash
python scripts/run_full_pipeline.py
```

Build the feature store and scorecard outputs:

```bash
python scripts/build_features.py
```

Run the mock sentiment and alternative-data engine:

```bash
python scripts/run_sentiment_engine.py
```

Run the mock financial narrative reframing engine:

```bash
python scripts/run_narrative_engine.py
```

Run the mock regime analysis and market-state engine:

```bash
python scripts/run_regime_engine.py
```

Run the mock ML Forecasting & Distributional Risk Engine:

```bash
python scripts/run_ml_forecasting.py
```

Run the portfolio optimisation and constraint engine:

```bash
python scripts/run_portfolio_optimisation.py
```

Run risk, stress testing and hedge engines:

```bash
python scripts/run_risk_engine.py
python scripts/run_stress_tests.py
python scripts/run_hedge_engine.py
```

Validate Alpaca credentials or pull optional Alpaca daily bars:

```bash
python scripts/pull_alpaca_data.py --account
python scripts/pull_alpaca_data.py --bars --symbols AAPL MSFT
```

Run tests:

```bash
pytest
```

Outputs are saved in `reports/outputs/`.

Key Sprint 4 outputs:

- `features_monthly.csv`
- `alt_text_documents.csv`
- `alt_entity_mentions.csv`
- `alt_sentiment_scores.csv`
- `alt_event_signals.csv`
- `alt_features_monthly.csv`
- `narrative_concepts.csv`
- `narrative_frames.csv`
- `narrative_semantic_distances.csv`
- `narrative_markov_transitions.csv`
- `narrative_reframing_features.csv`
- `regime_features.csv`
- `factor_regime_probabilities.csv`
- `chaos_regime_probabilities.csv`
- `informational_driver_model.csv`
- `regime_transition_matrix.csv`
- `regime_suitability_scores.csv`
- `regime_dashboard_summary.csv`
- `ml_forecasts_3m.csv`
- `ml_forecasts_6m.csv`
- `ml_forecasts_9m.csv`
- `ml_forecasts_12m.csv`
- `return_distribution_forecasts.csv`
- `dividend_cut_probability.csv`
- `drawdown_probability.csv`
- `probabilistic_validation.csv`
- `var_es_backtest_report.csv`
- `distribution_sensitivity_analysis.csv`
- `distribution_trading_research_signals.csv`
- `optimised_portfolio_score_weighted.csv`
- `optimised_portfolio_risk_parity.csv`
- `optimised_portfolio_mean_variance.csv`
- `optimised_portfolio_cvar_constrained.csv`
- `optimised_portfolio_dividend_income.csv`
- `optimised_portfolio_regime_aware.csv`
- `portfolio_trade_list.csv`
- `portfolio_constraint_report.csv`
- `portfolio_optimisation_summary.csv`
- `portfolio_risk_report.csv`
- `risk_contribution_report.csv`
- `stress_test_report.csv`
- `stress_test_contribution_report.csv`
- `hedge_recommendations.csv`
- `defensive_substitution_recommendations.csv`
- `risk_stress_hedge_summary.md`
- `stock_scorecard.csv`
- `recommendations_portfolio_aware.csv`
- `recommendations_clean_sheet.csv`
- `recommendations_llm_benchmark.csv`
- `branch_comparison_report.csv`
- `final_recommendations.csv`
