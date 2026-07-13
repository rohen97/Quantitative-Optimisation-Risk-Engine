# Architecture

The repository is organised as a modular quant platform, with production logic in `src/` and scripts as thin entry points.

- `data_ingestion`: universe, mock data and vendor adapter interfaces.
- `portfolio`: current holdings loading, exposure and concentration diagnostics.
- `features`: financial, dividend, valuation, liquidity, risk and portfolio-fit features.
- `sentiment` and `alternative_data`: rule-based text and risk-signal scaffolds.
- `regime`: rule-based regime classification and suitability scoring.
- `models`: conservative scorecard, placeholder forecasts and walk-forward interfaces.
- `optimisation`: proposed portfolio construction and constraint checks.
- `risk`: VaR, CVaR, drawdown, risk reports and stress tests.
- `hedging`: equity-only and optional institutional hedge recommendations.
- `reporting`: CSV and Markdown output writers.
