# The Wolf Quant Model

Portfolio-aware, regime-aware and sentiment-aware conservative listed-equity selection MVP for DACH, EU ex-DACH, UK, US, Mainland China and Hong Kong.

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

Run the constrained, regime-gated and explainable DRL allocation overlay:

```bash
python scripts/run_drl_pipeline.py
```

The DRL engine is a residual overlay, not a replacement for the selected optimiser. It proposes bounded active-weight deltas against the baseline optimiser, applies probabilistic regime gating and the Wolf Chaos risk throttle, then projects weights through hard constraints. The acceptance gate records whether the result is rejected, blended or accepted as a challenger, and final recommendations retain the baseline source separately from DRL challenger status.

Validate Alpaca credentials or pull optional Alpaca daily bars:

```bash
python scripts/pull_alpaca_data.py --account
python scripts/pull_alpaca_data.py --bars --symbols AAPL MSFT
python scripts/pull_alpaca_data.py --crypto-bars --symbols BTC/USD --start 2022-09-01 --end 2022-09-07
```

Pull Yahoo Finance daily bars through yfinance:

```bash
python scripts/pull_yfinance_data.py --symbols AAPL MSFT SAP.DE VOD.L
```

Configure and inspect the multi-source data layer:

```bash
python scripts/pull_external_data.py --status-only
python scripts/pull_external_data.py --start 2020-01-01
```

`configs/data_sources.yaml` maps providers to the full DACH, EU ex-DACH, UK, US, Mainland China and Hong Kong universe. Add private credentials to `.env` using the placeholders in `.env.example`. With `USE_MOCK_DATA=false`, the price loader queries every enabled provider for which credentials are available, cross-validates overlapping closes and retains the configured highest-priority observation. It does not silently treat a failed provider as valid data.

Configured sources include yfinance, Alpaca, EODHD, Finnhub, Alpha Vantage and iTick for market data; Frankfurter for FX; FRED, ECB, ONS, Bank of England, China Data and HKMA for economic and financial-system data. Alpha Vantage also exposes configured fundamental, FX, macro, commodity, news and sentiment capabilities. FRED and ECB requests preserve revision/vintage information where exposed. The supplied Medium articles are retained as non-authoritative engineering references; primary provider documentation controls endpoint and licensing decisions.

Mock mode remains the safe default. To use yfinance data in the model, set `USE_MOCK_DATA=false` and `DATA_PROVIDER=yfinance` in `.env`.

Run tests:

```bash
pytest
```

Outputs are saved in `reports/outputs/`.

Architecture diagrams and stage-by-stage diagnostic checks are documented in `docs/ARCHITECTURE_DIAGRAMS.md`.

## Data Backend Foundation

The model now has a DuckDB + Parquet data foundation underneath the existing CSV/mock pipeline. The default backend is still `legacy_csv`, so existing behaviour is preserved. Configure backend migration in `configs/data.yaml`:

- `legacy_csv`: current CSV/mock behaviour.
- `shadow`: compare legacy CSV outputs with DuckDB-backed snapshots while continuing to use legacy outputs.
- `duckdb`: read from DuckDB point-in-time views after validation.

The local DuckDB database path is `data/database/wolf.duckdb`. Large raw payloads stay outside the database under `data/raw_archive/`; DuckDB stores source, request hash, retrieval timestamp, status, row count, archive path and payload hash metadata.

Initialize and validate the data layer:

```bash
python scripts/init_database.py
python scripts/run_data_ingestion.py
python scripts/build_point_in_time_snapshots.py
python scripts/validate_data_layer.py
python scripts/compare_legacy_vs_duckdb.py
python scripts/export_duckdb_to_parquet.py
```

DuckDB files, SQLite files, raw API cache files and Parquet datasets are ignored by git. Do not commit raw vendor/API data or local database files.

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

## Investment Committee Reporting

The Investment Committee reporting layer consumes the pipeline outputs already saved in `reports/outputs/`. It does not rerun the model, alter optimiser selections, recalculate authoritative risk metrics or open any live execution path.

Run the report bundle:

```bash
python scripts/run_ic_reporting.py
python scripts/run_ic_reporting.py --skip-pdf
python scripts/run_ic_reporting.py --as-of-date 2026-06-30 --model-run-id ic-2026-06
python scripts/run_ic_reporting.py --backend legacy_csv --strict
```

Useful checks:

```bash
python scripts/run_ic_dashboard_check.py
python scripts/validate_ic_report.py
python scripts/render_ic_pdf.py
```

The immutable bundle is written to `reports/outputs/ic/<model_run_id>/`, and a copied latest view is written to `reports/outputs/ic/latest/`. HTML, Markdown and `report_bundle.json` are required. PDF and Streamlit dashboard support are optional; missing optional packages create warnings without breaking the core report. Critical portfolio inputs or HTML/bundle failures stop the full pipeline.

## Model Validation And Governance

The validation engine is a read-only downstream control layer. It validates point-in-time availability, leakage, forecast calibration, positive-loss VaR/Expected Shortfall, realised portfolio performance, transaction costs, benchmarks, regimes, constraints, DRL stability, sensitivity, ablations and governance. It does not tune or change the investment model.

```bash
python scripts/run_validation_smoke_test.py
python scripts/run_model_validation.py --mode full
python scripts/run_model_validation.py --mode release_candidate --strict
```

Every run is preserved under `reports/outputs/validation/<validation_run_id>/`; `reports/outputs/validation/latest/` is a copied view. Missing realised history is reported as `INSUFFICIENT_DATA`, never as a pass. Critical leakage, point-in-time, lineage, reproducibility or hard-constraint failures force `REJECTED`.

## Production Operations

The production operations layer wraps the existing model with scheduling, run locks, health checks, freshness checks, drift checks, alerting, incidents, manifests and latest-run pointers. It does not alter investment logic.

```bash
python scripts/run_production_pipeline.py --mode daily
python scripts/run_production_pipeline.py --mode weekly
python scripts/run_production_pipeline.py --mode monthly
python scripts/run_production_pipeline.py --mode release_candidate
```

See `docs/PRODUCTION_OPERATIONS.md` for Windows Task Scheduler setup, cron examples, alert routing and operator diagnostics.
