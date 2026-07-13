# Runbook

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the MVP pipeline:

```bash
python scripts/run_full_pipeline.py
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
