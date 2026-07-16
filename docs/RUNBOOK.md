# Runbook

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the MVP pipeline:

```bash
python scripts/run_full_pipeline.py
```

Build feature and scorecard outputs:

```bash
python scripts/build_features.py
```

Run sentiment and alternative-data outputs:

```bash
python scripts/run_sentiment_engine.py
```

Run narrative reframing outputs:

```bash
python scripts/run_narrative_engine.py
```

Run regime analysis outputs:

```bash
python scripts/run_regime_engine.py
```

Run ML distributional forecasting outputs:

```bash
python scripts/run_ml_forecasting.py
```

Run portfolio optimisation outputs:

```bash
python scripts/run_portfolio_optimisation.py
```

Run risk, stress and hedge outputs:

```bash
python scripts/run_risk_engine.py
python scripts/run_stress_tests.py
python scripts/run_hedge_engine.py
```

Validate Alpaca credentials:

```bash
python scripts/pull_alpaca_data.py --account
```

Pull Alpaca daily bars for selected symbols:

```bash
python scripts/pull_alpaca_data.py --bars --symbols AAPL MSFT
```

Run tests:

```bash
pytest
```

Outputs are written to `reports/outputs/`.

Key branch outputs:

- `recommendations_portfolio_aware.csv`
- `recommendations_clean_sheet.csv`
- `recommendations_llm_benchmark.csv`
- `branch_comparison_report.csv`
- `final_recommendations.csv`

The active universe is DACH, EU ex-DACH, UK, Mainland China and Hong Kong. The LLM analyst benchmark currently runs in mock mode and does not call OpenAI or Claude APIs.

Feature store output:

- `features_monthly.csv`

Scorecard output:

- `stock_scorecard.csv`

The scorecard uses neutral placeholder scores for unavailable production ML, regime and sentiment signals. These placeholders keep the pipeline reproducible while preserving the future production interface.

Alternative-data outputs:

- `alt_text_documents.csv`
- `alt_entity_mentions.csv`
- `alt_sentiment_scores.csv`
- `alt_event_signals.csv`
- `alt_features_monthly.csv`

The alternative-data engine runs in mock mode and does not call paid APIs or OpenAI/Claude. It flags risk conditions for review or exclusion; it does not override hard quant controls or create standalone buy signals.

Narrative reframing outputs:

- `narrative_concepts.csv`
- `narrative_frames.csv`
- `narrative_semantic_distances.csv`
- `narrative_markov_transitions.csv`
- `narrative_reframing_features.csv`

The narrative engine currently uses deterministic mock embeddings and local mock documents. Future providers such as FinBERT, Sentence-BERT, OpenAI embeddings or Claude/OpenAI analyst benchmarks can be added behind the existing interfaces.

Narrative validation fixtures live in `tests/fixtures/` and cover a known positive-to-risk deterioration path. They are used to validate concept drift, semantic-distance state assignment and Markov transition probabilities.

Regime outputs:

- `regime_features.csv`
- `factor_regime_probabilities.csv`
- `chaos_regime_probabilities.csv`
- `informational_driver_model.csv`
- `regime_transition_matrix.csv`
- `regime_suitability_scores.csv`
- `regime_dashboard_summary.csv`

The regime engine runs in mock mode only. It uses deterministic local factor, price, alternative-data and narrative proxies, then feeds regime suitability into scorecard scoring, recommendation branches, stress tests and hedge recommendations.

ML distributional outputs:

- `ml_forecasts_3m.csv`
- `ml_forecasts_6m.csv`
- `ml_forecasts_9m.csv`
- `ml_forecasts_12m.csv`
- `return_distribution_forecasts.csv`
- `dividend_cut_probability.csv`
- `drawdown_probability.csv`
- `probabilistic_validation.csv`
- `var_es_backtest_report.csv`
- `model_registry.csv`
- `distribution_sensitivity_analysis.csv`
- `distribution_trading_research_signals.csv`
- `distribution_research_extension_points.csv`

The ML layer is mock-first and forecasts distribution parameters, not just point returns. It derives VaR, CVaR, Expected Shortfall, tail risk, skewness risk and validation diagnostics. Transformer/xLSTM/CNN/LSTM ideas are present as disabled research placeholders; no deep-learning dependency or automated trading engine is active.

Portfolio optimisation outputs:

- `optimiser_input_dataset.csv`
- `optimised_portfolio_score_weighted.csv`
- `optimised_portfolio_risk_parity.csv`
- `optimised_portfolio_mean_variance.csv`
- `optimised_portfolio_cvar_constrained.csv`
- `optimised_portfolio_dividend_income.csv`
- `optimised_portfolio_regime_aware.csv`
- `portfolio_trade_list.csv`
- `portfolio_constraint_report.csv`
- `portfolio_optimisation_summary.csv`

The optimiser uses distributional forecasts, regime suitability, dividend risk, drawdown risk, narrative flags, alternative-data flags and current weights. In dry-run mode, if all names are excluded by upstream mock flags, a clearly marked fallback eligibility path selects the least-risky liquid names so optimisation outputs remain inspectable.

Risk, stress and hedge outputs:

- `portfolio_risk_report.csv`
- `risk_contribution_report.csv`
- `stress_test_report.csv`
- `stress_test_contribution_report.csv`
- `hedge_recommendations.csv`
- `defensive_substitution_recommendations.csv`
- `risk_stress_hedge_summary.md`

The risk engine uses the recommended optimised portfolio. Stress scenarios are deterministic mock shocks and optional institutional hedges are placeholders only.

Alpaca integration:

- Set `ENABLE_ALPACA=true`, `USE_MOCK_DATA=false`, `DATA_PROVIDER=alpaca`, `ALPACA_API_KEY_ID` and `ALPACA_API_SECRET_KEY` in `.env`.
- Paper trading account checks use `https://paper-api.alpaca.markets`.
- Market data bars use `https://data.alpaca.markets` and default to the `iex` feed.
- A `403 Forbidden` from `/v2/account` usually means missing, invalid or mismatched Alpaca auth headers.
- The full pipeline remains mock-first by default because the active universe includes non-US listings that Alpaca may not cover.
