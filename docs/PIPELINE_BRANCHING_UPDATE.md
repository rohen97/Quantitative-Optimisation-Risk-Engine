# Pipeline Branching Update — EU/UK Universe and Competing Model Branches

## Update Summary

The Wolf Quant Model equity universe is updated to remove India and add broader Europe and the United Kingdom.

## Revised Equity Universe

The stock-selection universe is listed equities only and now covers:

- DACH: Germany, Austria, Switzerland
- EU ex-DACH: broader European Union listed equities outside DACH
- UK: London-listed equities
- Mainland China / Shanghai listed equities
- Hong Kong listed equities

Removed from the active universe:

- India

## Revised Pipeline Architecture

The pipeline should branch before the main modelling stack so the model can generate and compare three separate recommendation pathways.

```text
Data Ingestion + Feature Store
        ↓
Universe: DACH + EU ex-DACH + UK + Shanghai/China + Hong Kong
        ↓
Branch 1: Portfolio-Aware Quant Model
        - Uses the current portfolio
        - Scores candidate equities by marginal portfolio contribution
        - Measures changes in concentration, income, VaR, CVaR and stress losses

Branch 2: Clean-Sheet Quant Model
        - Ignores the current portfolio
        - Builds a fresh conservative equity portfolio from cash
        - Useful as a benchmark against the portfolio-aware recommendation

Branch 3: LLM Analyst Benchmark Model
        - Uses OpenAI / Claude-style models as competing analyst engines
        - Produces structured thesis, risk, sentiment and valuation narratives
        - Does not directly override the quant model
        - Used for comparison, contradiction detection and qualitative risk review

        ↓
Branch Comparison Engine
        - Compare recommended stocks
        - Compare sector/country/currency exposure
        - Compare VaR/CVaR and stress losses
        - Compare dividend income and cash-flow quality
        - Identify consensus buys, disagreement names and rejected names

        ↓
Final Portfolio Construction
        - Optimisation
        - Risk management
        - Stress testing
        - Hedge recommendation
        - Dashboard and report outputs
```

## Branch 1: Portfolio-Aware Quant Model

Objective:

> Recommend stocks that improve the current portfolio.

Inputs:

- Existing holdings
- Current weights
- Sector/country/currency exposure
- Concentration metrics
- Current dividend income
- Current VaR/CVaR
- Current stress-test profile

Outputs:

- Buy/Hold/Avoid recommendation
- Target weight
- Incremental VaR/CVaR
- Incremental dividend income
- Incremental concentration impact
- Incremental sector/country/currency impact
- Portfolio fit score

## Branch 2: Clean-Sheet Quant Model

Objective:

> Build the best conservative equity portfolio without being constrained by current holdings.

Inputs:

- Same universe and features as the portfolio-aware model
- No current holdings constraint
- Starts from cash allocation

Outputs:

- Clean-sheet target portfolio
- Best conservative income equities
- Risk-adjusted expected return
- Dividend yield
- VaR/CVaR
- Stress-test behaviour

Use case:

- Benchmark the current-portfolio-aware recommendation against an unconstrained optimal portfolio.

## Branch 3: LLM Analyst Benchmark Model

Objective:

> Use OpenAI / Claude-style models as competing analyst engines to generate structured investment views.

This branch should not replace the quant model. It should act as an independent qualitative and reasoning benchmark.

Inputs:

- Company fundamentals
- Dividend data
- Cash-flow metrics
- Valuation data
- Sentiment and event signals
- Regime context
- Risk metrics

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

Use case:

- Identify when the quant model and LLM analyst model disagree.
- Flag names where the quantitative score is high but qualitative risks are severe.
- Produce investor-facing explanations for final recommendations.

## Branch Comparison Logic

The model should classify stocks into:

| Category | Meaning |
|---|---|
| Consensus Buy | Portfolio-aware quant, clean-sheet quant and LLM branch all support the stock |
| Quant Buy / LLM Caution | Quant score is strong but qualitative risks are flagged |
| LLM Buy / Quant Reject | Narrative is attractive but valuation, risk or dividend metrics fail |
| Portfolio-Aware Only | Stock improves current portfolio but is not in clean-sheet optimal portfolio |
| Clean-Sheet Only | Stock is attractive generally but does not improve current portfolio enough |
| Reject | Fails risk, quality, liquidity or dividend-safety filters |

## Final Recommendation Rule

The final model should prioritise:

1. Risk-adjusted portfolio improvement
2. Dividend safety
3. Free cash-flow quality
4. Balance-sheet strength
5. Regime suitability
6. Stress-test resilience
7. Hedgeability
8. Agreement or disagreement across model branches

The LLM branch should influence explanation, risk flags and disagreement analysis, but should not bypass hard quantitative risk controls.

## Required Code Refactor

Update configs:

- Remove India from allowed regions/countries/exchanges.
- Add EU ex-DACH and UK.
- Add branch configuration for:
  - `portfolio_aware_quant`
  - `clean_sheet_quant`
  - `llm_analyst_benchmark`

Update modules:

- `src/data_ingestion/universe.py`
- `src/models/scorecard.py`
- `src/optimisation/portfolio_builder.py`
- `src/reporting/report_writer.py`

Add modules:

- `src/branches/portfolio_aware.py`
- `src/branches/clean_sheet.py`
- `src/branches/llm_benchmark.py`
- `src/branches/branch_comparison.py`

Add outputs:

- `recommendations_portfolio_aware.csv`
- `recommendations_clean_sheet.csv`
- `recommendations_llm_benchmark.csv`
- `branch_comparison_report.csv`
- `final_recommendations.csv`
