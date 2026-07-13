from __future__ import annotations

import numpy as np
import pandas as pd


SECTORS = ["Healthcare", "Consumer Staples", "Utilities", "Financials", "Industrials", "Technology"]
REGIONS = [
    ("DACH", "Germany", "EUR"),
    ("DACH", "Switzerland", "CHF"),
    ("EU ex-DACH", "France", "EUR"),
    ("EU ex-DACH", "Netherlands", "EUR"),
    ("UK", "United Kingdom", "GBP"),
    ("Mainland China", "China", "CNY"),
    ("Hong Kong", "Hong Kong", "HKD"),
]


def generate_mock_universe(n: int = 24, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        region, country, currency = REGIONS[i % len(REGIONS)]
        sector = SECTORS[i % len(SECTORS)]
        rows.append(
            {
                "security_id": f"WOLF{i + 1:03d}",
                "ticker": f"WLF{i + 1:03d}",
                "company_name": f"Wolf {country} {sector} {i + 1}",
                "region": region,
                "country": country,
                "currency": currency,
                "sector": sector,
                "market_cap_usd": float(rng.uniform(1_000_000_000, 90_000_000_000)),
                "avg_daily_traded_value_usd": float(rng.uniform(2_000_000, 120_000_000)),
            }
        )
    return pd.DataFrame(rows)


def generate_mock_prices(universe: pd.DataFrame, days: int = 756, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 1)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    frames = []
    for idx, row in universe.reset_index(drop=True).iterrows():
        drift = rng.uniform(0.00005, 0.00045)
        vol = rng.uniform(0.008, 0.024)
        returns = rng.normal(drift, vol, size=len(dates))
        close = 40 * np.exp(np.cumsum(returns)) * (1 + idx / 40)
        frames.append(pd.DataFrame({"date": dates, "ticker": row["ticker"], "close": close, "return": returns}))
    return pd.concat(frames, ignore_index=True)


def generate_mock_fundamentals(universe: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 2)
    data = universe[["security_id", "ticker", "sector"]].copy()
    revenue = rng.uniform(1_000_000_000, 120_000_000_000, len(data))
    ebitda_margin = rng.uniform(0.08, 0.38, len(data))
    net_income_margin = rng.uniform(0.03, 0.22, len(data))
    fcf_margin = rng.uniform(0.04, 0.28, len(data))
    data["revenue"] = revenue
    data["revenue_growth"] = rng.uniform(-0.06, 0.16, len(data))
    data["ebitda"] = revenue * ebitda_margin
    data["ebitda_margin"] = ebitda_margin
    data["net_income"] = revenue * net_income_margin
    data["net_income_margin"] = net_income_margin
    data["operating_cash_flow"] = data["net_income"] * rng.uniform(0.9, 1.8, len(data))
    data["capex"] = revenue * rng.uniform(0.02, 0.10, len(data))
    data["free_cash_flow"] = revenue * fcf_margin
    data["total_debt"] = data["ebitda"] * rng.uniform(0.0, 4.0, len(data))
    data["cash"] = data["total_debt"] * rng.uniform(0.05, 0.70, len(data))
    data["shareholders_equity"] = revenue * rng.uniform(0.20, 0.80, len(data))
    data["enterprise_value"] = universe["market_cap_usd"].to_numpy() + data["total_debt"] - data["cash"]
    data["dividend_yield"] = rng.uniform(0.015, 0.065, len(data))
    data["trailing_12m_dps"] = rng.uniform(0.25, 4.5, len(data))
    data["dividend_growth_3y"] = rng.uniform(-0.02, 0.08, len(data))
    data["dividend_growth_5y"] = rng.uniform(-0.03, 0.10, len(data))
    data["payout_ratio"] = rng.uniform(0.25, 0.85, len(data))
    data["positive_fcf_years_5"] = rng.integers(2, 6, len(data))
    data["free_cash_flow_yield"] = data["free_cash_flow"] / universe["market_cap_usd"].to_numpy()
    data["fcf_margin"] = fcf_margin
    data["fcf_stability"] = rng.uniform(35, 95, len(data))
    data["cfo_to_net_income"] = data["operating_cash_flow"] / data["net_income"].replace(0, np.nan)
    data["net_debt_to_ebitda"] = (data["total_debt"] - data["cash"]) / data["ebitda"].replace(0, np.nan)
    data["interest_coverage"] = rng.uniform(2.0, 20.0, len(data))
    data["roe"] = rng.uniform(0.04, 0.24, len(data))
    data["roic"] = rng.uniform(0.03, 0.20, len(data))
    data["pe_ratio"] = rng.uniform(7, 30, len(data))
    data["pb_ratio"] = rng.uniform(0.7, 5.0, len(data))
    data["ev_ebitda"] = rng.uniform(4, 18, len(data))
    data["dividend_cut_flag_3y"] = rng.choice([0, 1], len(data), p=[0.85, 0.15])
    data["cet1_ratio"] = np.where(data["sector"].eq("Financials"), rng.uniform(0.10, 0.18, len(data)), np.nan)
    data["solvency_ratio"] = np.where(data["sector"].isin(["Financials", "Insurance"]), rng.uniform(1.2, 2.4, len(data)), np.nan)
    data["npl_ratio"] = np.where(data["sector"].eq("Financials"), rng.uniform(0.005, 0.06, len(data)), np.nan)
    data["book_value_growth"] = np.where(data["sector"].eq("Financials"), rng.uniform(-0.02, 0.12, len(data)), np.nan)
    return data


def generate_mock_current_portfolio(universe: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    holdings = universe.head(8).copy()
    rng = np.random.default_rng(seed + 3)
    holdings["shares"] = rng.integers(150, 1400, len(holdings))
    holdings["current_price"] = rng.uniform(20, 180, len(holdings))
    holdings["market_value_usd"] = holdings["shares"] * holdings["current_price"]
    holdings["dividend_yield"] = rng.uniform(0.02, 0.055, len(holdings))
    holdings["beta"] = rng.uniform(0.55, 1.25, len(holdings))
    holdings["volatility"] = rng.uniform(0.16, 0.32, len(holdings))
    return holdings[
        [
            "ticker",
            "company_name",
            "country",
            "region",
            "currency",
            "sector",
            "shares",
            "current_price",
            "market_value_usd",
            "dividend_yield",
            "beta",
            "volatility",
        ]
    ]


def generate_mock_sentiment(universe: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 4)
    data = universe[["security_id", "ticker"]].copy()
    data["news_sentiment_30d"] = rng.normal(0.08, 0.35, len(data)).clip(-1, 1)
    data["news_sentiment_90d"] = rng.normal(0.05, 0.25, len(data)).clip(-1, 1)
    data["negative_news_intensity"] = rng.uniform(0, 3.5, len(data))
    data["controversy_score"] = rng.uniform(0, 70, len(data))
    data["dividend_risk_score"] = rng.uniform(5, 85, len(data))
    data["management_confidence_score"] = rng.uniform(25, 95, len(data))
    data["regulatory_risk_score"] = rng.uniform(5, 90, len(data))
    data["credit_stress_score"] = rng.uniform(5, 85, len(data))
    data["ownership_flow_momentum"] = rng.normal(0, 1, len(data))
    data["liquidity_stress_score"] = rng.uniform(5, 90, len(data))
    return data
