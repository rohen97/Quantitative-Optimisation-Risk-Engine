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

Production ML, regime and sentiment engines are not built yet. Missing signals use neutral placeholder scores so the interface remains stable.

Output:

- `reports/outputs/stock_scorecard.csv`
