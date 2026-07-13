# Architecture

The repository is organised as a modular quant platform, with production logic in `src/` and scripts as thin entry points.

- `data_ingestion`: universe, mock data and vendor adapter interfaces.
- `branches`: portfolio-aware quant, clean-sheet quant, mock LLM analyst benchmark and branch comparison engines.
- `portfolio`: current holdings loading, exposure and concentration diagnostics.
- `features`: financial, dividend, valuation, liquidity, risk and portfolio-fit features.
- `sentiment` and `alternative_data`: rule-based text and risk-signal scaffolds.
- `regime`: rule-based regime classification and suitability scoring.
- `models`: conservative scorecard, placeholder forecasts and walk-forward interfaces.
- `optimisation`: proposed portfolio construction and constraint checks.
- `risk`: VaR, CVaR, drawdown, risk reports and stress tests.
- `hedging`: equity-only and optional institutional hedge recommendations.
- `reporting`: CSV and Markdown output writers.

## Active Universe

The active listed-equity universe covers DACH, EU ex-DACH, UK, Mainland China and Hong Kong. India is no longer part of the active stock-selection universe.

## Branching Pipeline

The pipeline runs three deterministic MVP branches before final optimisation/risk/stress/hedge outputs:

1. Portfolio-Aware Quant Model: prioritises current-portfolio improvement, dividend income, diversification and incremental risk.
2. Clean-Sheet Quant Model: ranks what the model would own from cash without existing holdings.
3. OpenAI / Claude Analyst Benchmark Model: mock structured analyst output for future provider integration.

The branch comparison engine flags agreement, disagreement and final review requirements. LLM agreement can increase confidence, but LLM output cannot override quant hard filters.

## Feature Store

The feature store converts mock or future vendor data into stock-level monthly features. Current modules cover dividend quality, cash-flow quality, balance-sheet strength, valuation, risk, liquidity and portfolio fit.

The output is `reports/outputs/features_monthly.csv`. Missing ML, regime and sentiment production signals use neutral placeholder scores until those engines are implemented.

## Conservative Scorecard

The scorecard applies hard filters before scoring. Filters cover equity instrument type, active listing status, market cap, liquidity, dividend yield, positive free cash flow, payout ratio, leverage, severe risk flags and incremental CVaR where available.

Scoring weights are configured around dividend safety, cash-flow quality, balance-sheet strength, valuation, regime suitability, ML expected risk-adjusted return, portfolio diversification benefit, liquidity and sentiment/alternative-data signal.
