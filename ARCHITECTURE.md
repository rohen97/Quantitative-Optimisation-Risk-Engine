# Architecture

The repository is organised as a modular quant platform, with production logic in `src/` and scripts as thin entry points.

- `data_ingestion`: universe, mock data and vendor adapter interfaces.
- `branches`: portfolio-aware quant, clean-sheet quant, mock LLM analyst benchmark and branch comparison engines.
- `portfolio`: current holdings loading, exposure and concentration diagnostics.
- `features`: financial, dividend, valuation, liquidity, risk and portfolio-fit features.
- `sentiment` and `alternative_data`: mock/local text ingestion, entity mapping, rule-based sentiment, event classification, rolling alternative-data features and risk overlays.
- `narrative`: financial concept extraction, occurrence/reoccurrence tracking, narrative frame construction, mock embeddings, semantic distance, temporal reframing and Markov transition analysis.
- `regime`: factor-regime lens, Wolf Chaos Index, informational regime drivers, fused dashboard, transition matrix and stock-level regime suitability scoring.
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

The feature store converts mock or future vendor data into stock-level monthly features. Current modules cover dividend quality, cash-flow quality, balance-sheet strength, valuation, risk, liquidity, sentiment/narrative overlays, regime suitability and portfolio fit.

The output is `reports/outputs/features_monthly.csv`. Missing ML, regime and sentiment production signals use neutral placeholder scores until those engines are implemented.

## Conservative Scorecard

The scorecard applies hard filters before scoring. Filters cover equity instrument type, active listing status, market cap, liquidity, dividend yield, positive free cash flow, payout ratio, leverage, severe risk flags and incremental CVaR where available.

Scoring weights are configured around dividend safety, cash-flow quality, balance-sheet strength, valuation, regime suitability, ML expected risk-adjusted return, portfolio diversification benefit, liquidity and sentiment/alternative-data signal.

## Sentiment And Alternative Data

The sentiment and alternative-data engine is a risk overlay, not a standalone buy signal. In mock mode it generates active-universe text documents, maps them to securities, scores sentiment with rule-based financial keyword dictionaries, classifies events and aggregates rolling monthly features.

Outputs include text documents, entity mentions, sentiment scores, event signals and `alt_features_monthly.csv`. The scorecard consumes sentiment/alt-data score, dividend risk, regulatory risk, governance red-flag count, credit stress and review/exclusion flags.

## Financial Narrative Reframing

The narrative engine looks beyond sentiment to detect how the equity story is being framed and reframed over time. It extracts financial concepts, tracks first occurrences and reoccurrences, builds co-occurring concept frames, embeds frames with a deterministic mock provider, measures semantic distance to risk/quality anchors, classifies temporal narrative states and estimates Markov transition probabilities.

Narrative features feed the scorecard as risk overlays: high risk reframing, dividend-risk similarity, credit-stress similarity, governance/regulatory similarity or negative-to-distress transition probability can trigger review, cap weights or exclude names. Narrative output cannot override hard quant risk controls.

## Regime Analysis And Market State

The regime engine is a market-state overlay that runs in deterministic mock mode. It builds a factor lens across Global, DACH, EU ex-DACH, UK, Mainland China and Hong Kong, estimates factor-regime probabilities, calculates a FCIX-lite Wolf Chaos Index, models informational deterioration drivers from alternative data and narrative features, fuses the signals into a dominant market regime and scores every stock for suitability under that regime.

Regime outputs feed the scorecard, portfolio-aware branch, clean-sheet branch, mock analyst benchmark, stress tests and hedge recommendations. The engine can reduce weights, trigger review/exclusion flags and add regime-conditioned stress/hedge overlays, but it cannot override hard quant controls.
