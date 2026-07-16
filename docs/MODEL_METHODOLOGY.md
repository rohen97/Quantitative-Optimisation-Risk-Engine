# Model Methodology

The MVP ranks listed equities with conservative hard filters, modular feature engineering, weighted quality scores, portfolio-fit features, branch comparison, risk checks, stress tests and hedge recommendations.

## Feature Store

The feature store creates stock-level monthly features from mock or future vendor inputs.

Feature groups:

- Dividend: yield, trailing DPS, 3Y/5Y growth, payout ratio, cut flag, stability, safety, FCF cover and dividend income.
- Cash-flow and quality: operating cash flow, capex, free cash flow, FCF yield, margins, CFO/net income, revenue growth, ROE, ROIC, earnings stability and cash-flow quality.
- Balance sheet: debt, cash, net debt, equity, net debt/EBITDA, debt/equity, interest coverage and sector-specific financial placeholders.
- Valuation: market cap, enterprise value, PE, PB, EV/EBITDA, FCF yield, dividend yield spread and cross-sectional valuation percentile.
- Risk: daily return, annualised volatility, beta placeholders, max drawdown, downside volatility, VaR, CVaR, Sharpe proxy, Sortino proxy and risk score.
- Liquidity: average daily value, average volume, turnover, days to liquidate 1% NAV, liquidity score and liquidity stress.
- Portfolio fit: correlation fallback, incremental exposures, incremental dividend income, concentration impact, diversification benefit and portfolio fit score.
- Sentiment and alternative data: rolling news sentiment, controversy, dividend risk, cash-flow deterioration, management confidence, regulatory risk, litigation risk, governance flags, credit stress, abnormal attention and event severity.
- Narrative reframing: financial concept extraction, first occurrence/reoccurrence tracking, frame construction, semantic drift, risk-anchor similarity, temporal narrative states and Markov transition probabilities.
- Regime analysis: factor-regime probabilities, Wolf Chaos Index, informational regime drivers, fused market-state dashboard, transition matrix and stock-level regime suitability.
- Distributional ML forecasting: expected total return, volatility, dividend-cut probability, drawdown probability, Normal/Student-t/skewed Student-t parameters, VaR, CVaR, Expected Shortfall, tail risk and skewness risk.

Output:

- `reports/outputs/features_monthly.csv`

## Conservative Scorecard

Hard filters are applied before scoring:

- Instrument type must be Equity.
- Listing status must be Active.
- Market cap and average daily value must clear configured minimums.
- Dividend yield must clear the configured minimum unless later overridden.
- Free cash flow must be positive where available.
- Payout ratio and non-financial leverage must stay below configured maximums.
- Liquidity score must clear the configured minimum.
- Severe regulatory, governance, credit or CVaR flags are excluded where available.

Weighted score:

- 18% Dividend Safety
- 18% Cash Flow Quality
- 14% Balance Sheet Strength
- 10% Valuation
- 10% Regime Suitability
- 10% ML Expected Risk-Adjusted Return
- 8% Portfolio Diversification Benefit
- 5% Liquidity
- 7% Sentiment / Alternative Data Signal

Production ML and real vendor ingestion are not built yet. Missing signals use neutral placeholder scores so the interface remains stable.

## Sentiment + Alternative Data Methodology

The sentiment engine is designed as an early-warning risk overlay. It currently runs in mock mode and supports the following source types by design: news, exchange announcements, annual/interim reports, earnings transcripts, analyst commentary, regulatory filings, social media, search trends, ownership/flow data and credit signals.

The mock pipeline:

1. Generates local text documents for active-universe companies.
2. Maps documents to securities using ticker and company-name mentions.
3. Scores text with rule-based financial sentiment dictionaries.
4. Classifies events such as dividend cuts, profit warnings, buybacks, regulatory probes, credit stress and litigation.
5. Aggregates rolling stock-level alternative-data features.
6. Produces risk flags for scorecard and risk-engine consumption.

Sentiment can reduce confidence, trigger review, cap target weights or exclude severe-risk names through hard risk overlays. It cannot override failed quant filters and cannot turn a weak quant name into a final buy by itself.

## Financial Narrative Reframing Methodology

The Financial Narrative Reframing Engine adapts protocol-framing ideas to financial text. It is more than sentiment analysis: it measures whether the company story is shifting from one frame to another over time.

Current mock-mode process:

1. Generate local financial documents for active-universe companies.
2. Extract concepts such as dividend, cash flow, margin pressure, credit stress, regulation, governance and distress.
3. Track first occurrence, reoccurrence, recurring risk concepts and concept acceleration.
4. Construct narrative frames from co-occurring concepts.
5. Generate deterministic mock embeddings for frame text.
6. Measure cosine distance to company history and anchors such as positive quality, distress, dividend risk, credit stress, governance risk and regulatory risk.
7. Classify temporal states such as positive stable, negative deteriorating, dividend risk, credit stress, regulatory overhang and distress.
8. Estimate first-order and second-order Markov transition probabilities between narrative states.
9. Aggregate final narrative reframing features for the scorecard and risk overlays.

Narrative outputs can trigger review, cap weights or exclude severe-risk names. They cannot override hard quant filters or act as standalone buy signals.

Future upgrades can add FinBERT, Sentence-BERT, OpenAI embeddings, Claude/OpenAI analyst benchmark integration and real vendor documents.

Known-scenario fixtures in `tests/fixtures/` validate that a timeline can move from a positive quality frame into governance risk, distress and credit stress, with expected Markov transitions.

## Regime Analysis Methodology

The Regime Analysis and Market State Engine is a deterministic mock-mode overlay inspired by factor-regime modeling and chaos/systemic-risk indicators. It does not fetch real macro, market or paid data yet.

Current process:

1. Build a regional factor lens for Global, DACH, EU ex-DACH, UK, Mainland China and Hong Kong.
2. Standardise factor returns and estimate crisis, steady-state, inflation and walking-on-ice probabilities with a GMM when available, falling back to rules.
3. Calculate the Wolf Chaos Index from cross-sectional dispersion, pairwise correlation, correlation instability, largest eigenvalue, effective bets, breadth, volatility-of-volatility and drawdown breadth.
4. Estimate informational regime deterioration using alternative-data and narrative proxies.
5. Fuse factor, chaos and informational signals into a dominant regime such as steady-state low chaos, crisis high chaos, inflation pressure, Europe recession, China policy stress, UK rate pressure, credit stress or mixed transition.
6. Build a transition matrix and stock-level regime suitability scores.
7. Feed suitability, review/exclusion flags and target-weight adjustments into the scorecard, branches, stress tests and hedge recommendations.

Regime output is a risk and sizing overlay. It can reduce exposure, add reviews or exclude severe mismatch names, but it cannot override hard filters.

## ML Forecasting And Distributional Risk Methodology

The ML layer follows the paper-inspired idea that financial models should forecast return distributions rather than only point estimates. In the current mock implementation, the engine estimates distribution parameters:

- Normal: `mu`, `sigma`
- Student-t: `mu`, `sigma`, `nu`
- Skewed Student-t placeholder: `mu`, `sigma`, `nu`, `xi`

`mu` is conditional expected total return, `sigma` is conditional volatility, `nu` controls tail thickness and `xi` controls skewness. The current skewed Student-t implementation is documented as an approximation: it widens downside or upside tails around a Student-t base and is designed to be replaced later with a full implementation.

The engine derives P5/P50/P95, VaR 5%, VaR 1%, CVaR, Expected Shortfall, tail-risk score, skewness-risk score, forecast uncertainty and distribution model confidence. Probabilistic validation includes Log Predictive Score, CRPS approximation, PIT diagnostics, quantile coverage and calibration error. VaR/ES backtesting includes exceedance rates and a Kupiec test, with placeholders for Christoffersen independence and richer ES tests.

Future research hooks are present but disabled or research-only: additional asset classes, Transformer/xLSTM/CNN/LSTM distributional forecasters, sensitivity analysis, quantile-based forecasting, conformal prediction and distribution-derived trading signal research. No automated trading, DRL or deep-learning dependency is enabled.

## Portfolio Optimisation Methodology

The Portfolio Optimisation and Constraint Engine turns model outputs into target weights and trade recommendations. It consumes current holdings, scorecard scores, portfolio-fit features, sentiment and narrative risk flags, regime suitability and distributional ML forecasts including expected return, volatility, VaR, CVaR, Expected Shortfall, dividend-cut probability, drawdown probability, tail risk and skewness risk.

Implemented constructors:

- Equal-weight eligible fallback.
- Score-weighted portfolio.
- Risk-parity portfolio using volatility proxies.
- Mean-variance baseline using expected return and variance penalty.
- CVaR / Expected Shortfall constrained portfolio.
- Dividend-income constrained portfolio.
- Regime-aware portfolio.

Hard constraints include long-only weights, single-name caps, liquidity, active equity status and exclusion flags. Soft constraints include dividend yield, volatility, VaR, CVaR, Expected Shortfall, turnover, HHI, effective holdings and concentration limits. The constraint report records breaches rather than hiding them.

The trade list compares current and target weights and assigns Buy, Increase, Reduce, Sell, Hold or Avoid actions. Optimisation cannot override hard exclusions or use high expected return alone to justify high-risk names. Future upgrades can add Hierarchical Risk Parity, Black-Litterman, transaction-cost models, tax constraints, robust covariance estimation, robust optimisation and a DRL allocation overlay.

Output:

- `reports/outputs/stock_scorecard.csv`
