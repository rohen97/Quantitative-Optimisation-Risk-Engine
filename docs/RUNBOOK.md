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

Alpaca integration:

- Set `ENABLE_ALPACA=true`, `USE_MOCK_DATA=false`, `DATA_PROVIDER=alpaca`, `ALPACA_API_KEY_ID` and `ALPACA_API_SECRET_KEY` in `.env`.
- Paper trading account checks use `https://paper-api.alpaca.markets`.
- Market data bars use `https://data.alpaca.markets` and default to the `iex` feed.
- A `403 Forbidden` from `/v2/account` usually means missing, invalid or mismatched Alpaca auth headers.
- The full pipeline remains mock-first by default because the active universe includes non-US listings that Alpaca may not cover.
