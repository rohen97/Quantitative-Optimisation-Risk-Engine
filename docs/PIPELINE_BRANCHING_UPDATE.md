# Pipeline Branching Update - EU/UK Universe and Competing Model Branches

## Update Summary

The Wolf Quant Model equity universe is updated to remove India and add broader Europe and the United Kingdom.

## Revised Equity Universe

The stock-selection universe is listed equities only and now covers:

- DACH: Germany, Austria, Switzerland
- EU ex-DACH: broader European Union listed equities outside DACH
- UK: London-listed equities
- Mainland China / Shanghai listed equities
- Hong Kong listed equities

India has been removed from the active equity universe. Options and ETFs remain out of scope unless explicitly configured later.

## Revised Pipeline Architecture

The pipeline branches before final optimisation, risk, stress and hedge outputs so the model can compare three separate recommendation pathways.

```text
Data Ingestion + Feature Store
        |
Universe: DACH + EU ex-DACH + UK + Shanghai/China + Hong Kong
        |
Branch 1: Portfolio-Aware Quant Model
        |
Branch 2: Clean-Sheet Quant Model
        |
Branch 3: LLM Analyst Benchmark Model
        |
Branch Comparison Engine
        |
Final Recommendations
        |
Optimisation + Risk + Stress + Hedge Outputs
```

## Branch 1: Portfolio-Aware Quant Model

Objective: recommend stocks that improve the current portfolio.

Inputs:

- Existing holdings
- Current weights
- Sector/country/currency exposure
- Concentration metrics
- Current dividend income
- Current risk metrics where available
- Conservative scorecard

Outputs:

- Buy/Hold/Avoid recommendation
- Portfolio-aware target weight
- Incremental dividend income
- Incremental concentration impact
- Incremental sector/country/currency impact
- Incremental risk impact
- Portfolio fit score

Output file:

- `recommendations_portfolio_aware.csv`

## Branch 2: Clean-Sheet Quant Model

Objective: build the best conservative equity portfolio without being constrained by current holdings.

Inputs:

- Same universe and scorecard features as the portfolio-aware model
- No current holdings constraint
- Starts from cash allocation

Outputs:

- Clean-sheet recommendation
- Clean-sheet rank
- Clean-sheet target weight

Output file:

- `recommendations_clean_sheet.csv`

## Branch 3: LLM Analyst Benchmark Model

Objective: use OpenAI / Claude-style models as competing analyst engines to generate structured investment views.

This branch is currently mock-only. It does not call real provider APIs, does not require API keys and cannot override hard quant risk controls.

Structured output per stock:

- Investment thesis
- Key risks
- Dividend safety view
- Cash-flow quality view
- Regulatory/governance concerns
- Bull/base/bear narrative
- Qualitative score
- Recommendation: Buy / Hold / Avoid
- Confidence score

Output file:

- `recommendations_llm_benchmark.csv`

## Branch Comparison Logic

The model classifies stocks into:

| Category | Meaning |
|---|---|
| Consensus Buy | Portfolio-aware quant, clean-sheet quant and LLM branch all support the stock |
| Quant Buy / LLM Caution | Quant score is strong but qualitative risks are flagged |
| LLM Buy / Quant Reject | Narrative is attractive but valuation, risk or dividend metrics fail |
| Portfolio-Aware Only | Stock improves current portfolio but is not in clean-sheet optimal portfolio |
| Clean-Sheet Only | Stock is attractive generally but does not improve current portfolio enough |
| Reject | Fails risk, quality, liquidity or dividend-safety filters |

Output files:

- `branch_comparison_report.csv`
- `final_recommendations.csv`

## Final Recommendation Rule

The final model prioritises:

1. Risk-adjusted portfolio improvement
2. Dividend safety
3. Free cash-flow quality
4. Balance-sheet strength
5. Stress-test resilience
6. Agreement or disagreement across model branches

LLM agreement can increase confidence. LLM disagreement should trigger review. LLM output cannot bypass quant hard filters.

## MVP Implementation Status

Implemented:

- `src/branches/portfolio_aware.py`
- `src/branches/clean_sheet.py`
- `src/branches/llm_benchmark.py`
- `src/branches/branch_comparison.py`
- `configs/branching.yaml`
- Branch output wiring in `src/pipeline.py`

Verified:

- `python scripts/run_full_pipeline.py`
- `pytest`
