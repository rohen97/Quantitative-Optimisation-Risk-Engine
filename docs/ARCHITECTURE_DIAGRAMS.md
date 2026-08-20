# Wolf Quant Model Architecture Diagrams

This document gives a visual map of The Wolf Quant Model from data ingestion through final governance. The diagrams are written in Mermaid so GitHub renders them directly.

## Executive Flow

```mermaid
flowchart LR
    A[External and Local Data] --> B[Raw Layer]
    B --> C[Clean Layer]
    C --> D[Model-Ready Point-in-Time Snapshots]
    D --> E[Feature, Sentiment, Narrative and Regime Engines]
    E --> F[Distributional Forecasts and Conservative Scorecard]
    E --> S[Supervised Alpha Model Zoo]
    F --> G[Recommendation Branches]
    G --> H[Constrained Optimiser Baseline]
    H --> I[Risk, Stress and Hedge Engines]
    H --> J[DRL Residual Overlay Challenger]
    H --> U[Governed Supervised Return Overlay]
    S --> U
    I --> K[Final Portfolio Resolution]
    J --> K
    U --> K
    K --> L[Investment Committee Reporting]
    L --> M[Validation and Governance]
```

The model is intentionally layered. Forecasts, scorecards and DRL proposals can influence recommendations, but hard portfolio constraints, risk governance and validation gates remain downstream controls.

## Full Pipeline

```mermaid
flowchart TD
    S01[01 Data Ingestion and Point-in-Time Snapshots] --> S02[02 Current Portfolio Engine]
    S02 --> S03[03 Feature Store]
    S03 --> S04[04 Sentiment and Alternative Data]
    S04 --> S05[05 Narrative Reframing]
    S05 --> S06[06 Regime Engine]
    S06 --> S07[07 ML and Distributional Forecasting]
    S07 --> S08[08 Conservative Stock Scorecard]
    S08 --> S09[09 Portfolio-Aware Branch]
    S08 --> S10[10 Clean-Sheet Branch]
    S08 --> S11[11 LLM Benchmark Branch]
    S09 --> S12[12 Branch Comparison]
    S10 --> S12
    S11 --> S12
    S12 --> S13[13 Portfolio Optimisation]
    S13 --> S14[14 Risk Engine]
    S14 --> S15[15 Stress Testing]
    S15 --> S16[16 Hedge Recommendations]
    S13 --> S17[17 DRL Overlay]
    S16 --> S18[18 Final Portfolio Resolution]
    S17 --> S18
    S18 --> S19[19 Investment Committee Dashboard and Reporting Engine]
    S19 --> S20[20 Validation and Governance]

    S03 -. separate governed research runner .-> MLZ[Supervised Model Zoo]
    MLZ --> CV[Expanding Purged Cross-Validation]
    CV --> ENS[Rank-Normalised Ensemble]
    ENS --> GATE[Supervised Acceptance Gate]
    S13 --> GATE
    GATE -. positive blend only .-> S14
```

The numbered 20-stage run remains the deterministic production baseline. The
supervised-alpha runner is deliberately separate: it can feed expected returns
back into optimisation only after its independent evidence gate assigns a
positive blend. Its current blend is zero.

## Data Architecture

```mermaid
flowchart TD
    subgraph Sources[Data Sources]
        YF[yfinance]
        TDB[TickDB]
        AK[AKShare]
        OBB[OpenBB Provider Checks]
        ALP[Alpaca]
        EOD[EODHD]
        FIN[Finnhub]
        SEC[SEC EDGAR]
        FIGI[OpenFIGI]
        FRED[FRED and ALFRED]
        ECB[ECB]
        FX[Frankfurter FX]
        CHN[China Data]
        HK[HKMA]
        FILES[CSV and Excel Portfolio Files]
    end

    Sources --> RAW[Raw Retrieval Metadata]
    RAW --> ARCH[data/raw_archive files]
    RAW --> CLEAN[Clean Typed Tables]
    CLEAN --> PIT[Point-in-Time Views and Snapshots]
    PIT --> CSV[Legacy CSV Outputs]
    PIT --> DUCK[DuckDB Audit Store]
    PIT --> PARQ[Parquet Archives]
    CSV --> MODEL[Model Engines]
    DUCK --> MODEL
```

Key design rules:

- Raw payloads are archived outside DuckDB by default.
- DuckDB stores metadata, lineage, hashes, availability dates and typed clean tables.
- Macro revisions are inserted as new vintages rather than overwritten.
- `legacy_csv` remains the default backend until shadow comparisons and validation justify switching reads to DuckDB.
- Provider adapters normalise data before model code sees it.

## Portfolio Decision Stack

```mermaid
flowchart TD
    CP[Current Portfolio] --> DIAG[Portfolio Diagnostics]
    FEAT[Feature Store] --> SCORE[Conservative Scorecard]
    FORE[Distributional Forecasts] --> SCORE
    FEAT --> SUP[Supervised Alpha Model Zoo]
    REG[Regime State] --> SCORE
    SENT[Sentiment and Narrative] --> SCORE
    SCORE --> PA[Portfolio-Aware Branch]
    SCORE --> CS[Clean-Sheet Branch]
    SCORE --> LLM[LLM Benchmark Branch]
    PA --> COMP[Branch Comparison]
    CS --> COMP
    LLM --> COMP
    COMP --> OPT[Constrained Classical Optimiser]
    OPT --> BASE[Baseline Portfolio]
    SUP --> SGATE[Supervised Acceptance Gate]
    BASE --> SOVER[Governed Expected-Return Overlay]
    SGATE --> SOVER
    SOVER --> SOPT[Supervised Challenger Optimiser]
    BASE --> DRL[DRL Residual Challenger]
    BASE --> FINAL[Final Portfolio Resolver]
    SOPT --> FINAL
    DRL --> FINAL
```

The optimiser is the primary allocator because it is deterministic and directly governed by explicit mandate, risk, concentration, liquidity and turnover constraints.

## Supervised ML Research Architecture

```mermaid
flowchart LR
    PIT[Point-in-Time Feature Panel] --> LABEL[Peer-Relative Matured Labels]
    LABEL --> PREP[Fold-Local Preprocessing and Screening]

    subgraph Zoo[Model Zoo]
        LIN[OLS Screened, Ridge, Elastic Net, Huber]
        TREE[Random Forest, Extra Trees, Histogram Boosting, XGBoost]
        RANK[XGBoost Ranker]
    end

    PREP --> LIN
    PREP --> TREE
    PREP --> RANK
    LIN --> CV[Expanding Purged Walk-Forward CV]
    TREE --> CV
    RANK --> CV
    CV --> WIN[One Winner per Family]
    WIN --> ENS[Rank-Normalised Linear, Tree and Ranker Ensemble]
    ENS --> UNC[Conformal Uncertainty and Cost Adjustment]
    UNC --> ACCEPT[Independent-Evidence Acceptance Gate]
    ACCEPT -->|positive blend| OVER[Blend into Expected Returns]
    ACCEPT -->|zero blend| NOOP[Baseline No-Op]
    OVER --> OPT[Regional Constrained Optimiser]
    NOOP --> OPT

    CODE[src/models/supervised_alpha.py] -. implementation .-> Zoo
    CFG[configs/ml_forecasting.yaml] -. families and gates .-> PREP
    RUN[scripts/run_supervised_alpha.py] -. orchestration .-> CV
    CV --> LOCAL[data/processed/supervised_alpha model bundles]
    CV --> PUBLIC[reports/outputs/supervised_alpha aggregate evidence]
```

Trained bundles and resumable checkpoints are local. GitHub receives aggregate
family winners, validation/OOS summaries, calibration, acceptance decisions,
model manifests and plots, but not security-level licensed-derived predictions.

## DRL Residual Overlay

```mermaid
flowchart TD
    BASE[Baseline Optimiser Weights] --> RAW[Raw DRL Action]
    STATE[Point-in-Time DRL State] --> RAW
    RAW --> BOUND[Bound Residual Deltas]
    BOUND --> GATE[Regime Specialist Gating]
    GATE --> THROTTLE[Wolf Chaos Risk Throttle]
    THROTTLE --> ADD[Add Deltas to Baseline]
    ADD --> MASK[Zero Excluded Assets]
    MASK --> PROJECT[Project to Hard Constraints]
    PROJECT --> ACCEPT[Acceptance and Rejection Gate]
    ACCEPT -->|accepted or blended| CHAL[DRL Challenger or Blend]
    ACCEPT -->|rejected| FALLBACK[Baseline Fallback]
    CHAL --> FINAL[Final Portfolio Resolution]
    FALLBACK --> FINAL
```

DRL is a challenger overlay, not an unrestricted replacement. In dry-run mode, the maximum DRL blend is capped at 25 percent and full replacement is disabled.

## Reporting And Governance

```mermaid
flowchart LR
    OUT[Pipeline Outputs] --> IC[IC Reporting Bundle]
    IC --> HTML[HTML Report]
    IC --> MD[Markdown Summary]
    IC --> PDF[Optional PDF]
    IC --> JSON[Report Bundle JSON]
    IC --> VAL[Validation Engine]
    VAL --> SCORE[Approval Scorecard]
    VAL --> GOV[Governance Decision]
    GOV -->|PASS| MONITOR[Candidate for Monitoring]
    GOV -->|WARNING| REVIEW[Human Review Required]
    GOV -->|REJECTED| BLOCK[Do Not Approve]
```

The validation engine is read-only. It does not tune forecasts, change weights or promote DRL. It evaluates whether the artifacts are fit for use.

## Sanity Checks And Diagnostics By Stage

| Stage | Diagnostics and Sanity Checks |
| --- | --- |
| Data ingestion and point-in-time snapshots | Provider status, request metadata, row counts, duplicate key checks, invalid currency checks, negative price checks, future `available_from` checks, input snapshot hashing, legacy-vs-DuckDB shadow comparison where enabled. |
| Current portfolio engine | Required column validation, CSV/Excel load checks, finite numeric checks, total NAV, weights summing to one, concentration, HHI, effective holdings and exposure summaries. |
| Feature store | Deterministic feature order, finite feature values, no future target columns, active universe coverage, region/country/currency alignment and missing-data diagnostics. |
| Sentiment and alternative data | Text document schema checks, entity/security mapping checks, event classification coverage, rolling feature aggregation checks and risk flag outputs. |
| Narrative reframing | Concept extraction coverage, frame construction, semantic distance sanity checks, transition probability normalisation and non-causal narrative labels. |
| Regime engine | Factor-regime probability sums, chaos-regime probability sums, Wolf Chaos Index bounds, transition matrix checks and dominant/secondary regime diagnostics. |
| ML and distributional forecasting | Forecast horizon labelling, finite P5/P50/P95 values, quantile ordering, VaR/CVaR/Expected Shortfall sign convention, forecast confidence bounds and probabilistic validation outputs. |
| Supervised benchmark-relative alpha | Matured target dates, fold-local preprocessing, purge and embargo boundaries, family-level convergence, expanding validation completeness, rank IC, independent cohort counts, sign tests, turnover/cost drag, conformal coverage, prospective freeze and zero-blend fallback. |
| Conservative scorecard | Hard exclusion filters, score component bounds, missing signal fallback checks, review flags and active universe membership. |
| Recommendation branches | Portfolio-aware and clean-sheet output schemas, LLM benchmark isolation, no LLM override of hard controls and branch disagreement flags. |
| Branch comparison | Consensus category assignment, disagreement commentary, missing branch handling and final review flags. |
| Portfolio optimisation | Long-only checks, sum-to-one checks, single-name caps, sector/country/region/currency caps, liquidity caps, turnover caps, cash floor and fallback portfolio generation. |
| Risk engine | Portfolio VaR, CVaR, Expected Shortfall, drawdown proxy, concentration, dividend-cut risk, liquidity risk and risk contribution ranking checks. |
| Stress testing | Required scenario coverage, portfolio loss percentage, portfolio loss USD, top contributor checks, hedge-required flags and post-stress value checks. |
| Hedge recommendations | Separation of equity substitutions from optional institutional hedge concepts, implementation complexity labels, cost/trade-off commentary and non-execution labels. |
| DRL overlay | State dimensions, eligibility mask, cash included, action bounds, hard constraint projection, turnover cap, risk throttle, fallback use, multi-seed stability, benchmark labels, ablations and non-causal explanations. |
| Final portfolio resolution | Explicit source precedence, invalid weight rejection, baseline/DRL challenger separation, accepted/rejected/blended status and final selected weight source. |
| IC reporting | Required HTML/Markdown/bundle artifacts, source lineage, deterministic narratives, chart generation, readiness status, report warnings and optional PDF handling. |
| Validation and governance | Leakage checks, chronological alignment, purge/embargo checks, forecast calibration, binary calibration, VaR backtesting, benchmark comparison, constraint validation, DRL validation, sensitivity, ablations, approval score and immutable run manifest. |

## Core Output Flow

```mermaid
flowchart TD
    RAW[Raw and Clean Data] --> FEATURES[features_monthly.csv]
    FEATURES --> FORECASTS[ml_forecasts and return_distribution_forecasts]
    FEATURES --> SUP[supervised_alpha validation and OOS summaries]
    FEATURES --> SCORECARD[stock_scorecard.csv]
    FORECASTS --> SCORECARD
    SCORECARD --> BRANCHES[branch recommendation CSVs]
    BRANCHES --> OPT[optimised_portfolio files]
    SUP --> SGATE[supervised acceptance decision]
    OPT --> SGATE
    SGATE --> SOPT[governed supervised optimiser input and local challenger]
    OPT --> RISK[portfolio_risk_report.csv]
    RISK --> STRESS[stress_test_report.csv]
    STRESS --> HEDGE[hedge_recommendations.csv]
    OPT --> DRL[drl_challenger and acceptance outputs]
    DRL --> FINAL[final_recommendations.csv]
    SOPT --> FINAL
    HEDGE --> FINAL
    FINAL --> IC[reports/outputs/ic/latest]
    IC --> VALIDATION[reports/outputs/validation/latest]
```

## Governance Interpretation

```mermaid
stateDiagram-v2
    [*] --> RunPipeline
    RunPipeline --> GenerateICReport
    GenerateICReport --> RunValidation
    RunValidation --> Approved: all critical controls pass
    RunValidation --> ReviewRequired: warnings or insufficient evidence
    RunValidation --> Rejected: critical control failure
    Rejected --> BaselineOnly: DRL rejected or hard constraints fail
    ReviewRequired --> HumanReview
    Approved --> Monitor
```

A successful script run does not automatically mean the model is approved. The governance status is the authority for deployment readiness.

