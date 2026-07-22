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

Run DRL allocation overlay outputs:

```bash
python scripts/run_drl_environment_check.py
python scripts/run_drl_training.py
python scripts/run_drl_backtest.py
python scripts/run_drl_explainability.py
python scripts/run_drl_pipeline.py
```

The DRL scripts run in mock mode unless `configs/drl.yaml` is changed. They load the selected optimiser baseline, construct point-in-time states, validate state dimensions and eligibility masks, run the market environment smoke test, train PPO or deterministic mock fallback, run walk-forward and multi-seed backtests, apply regime gating and the Wolf Chaos throttle, project actions through hard constraints, compare benchmarks, run ablations, generate explanations, build the DRL trade list and save the acceptance decision.

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

The active universe is DACH, EU ex-DACH, UK, US, Mainland China and Hong Kong. The LLM analyst benchmark currently runs in mock mode and does not call OpenAI or Claude APIs.

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

DRL overlay outputs:

- `drl_state_schema.csv`
- `drl_training_summary.csv`
- `drl_seed_results.csv`
- `drl_backtest_results.csv`
- `drl_benchmark_comparison.csv`
- `drl_acceptance_decision.csv`
- `drl_baseline_portfolio.csv`
- `drl_challenger_portfolio.csv`
- `drl_final_selected_weights_source.csv`
- `drl_target_weights.csv`
- `drl_trade_list.csv`
- `drl_constraint_adjustments.csv`
- `drl_reward_decomposition.csv`
- `drl_regime_agent_weights.csv`
- `drl_explanations.csv`
- `drl_feature_attributions.csv`
- `drl_asset_time_attributions.csv`
- `drl_ablation_results.csv`
- `drl_model_card.md`
- `drl_validation_report.md`

The DRL layer is a challenger overlay only. It cannot override hard exclusions, eligibility masks, liquidity restrictions, regime/narrative exclusions or stress-test rejection rules.

Operational checks:

- `drl_baseline_portfolio.csv` is the selected optimiser baseline.
- `drl_challenger_portfolio.csv` is the projected DRL challenger.
- `drl_acceptance_decision.csv` records rejected, blended or accepted status.
- `drl_final_selected_weights_source.csv` records the final source and blend weights.
- `final_recommendations.csv` keeps original recommendation fields and adds DRL challenger status. It does not silently replace optimiser weights.
- `drl_model_card.md` documents role, state/action design, reward, PPO, specialists, explainability, limitations and future research.
- `drl_validation_report.md` documents walk-forward validation, multiple seeds, benchmark fairness, ablations and acceptance/rejection controls.

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
- The full pipeline remains mock-first by default because the active universe includes both US and non-US listings; Alpaca may be useful for US names but does not cover the full universe.
