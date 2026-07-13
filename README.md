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

Run tests:

```bash
pytest
```

Outputs are saved in `reports/outputs/`.

Key Sprint 4 outputs:

- `features_monthly.csv`
- `stock_scorecard.csv`
- `recommendations_portfolio_aware.csv`
- `recommendations_clean_sheet.csv`
- `recommendations_llm_benchmark.csv`
- `branch_comparison_report.csv`
- `final_recommendations.csv`
