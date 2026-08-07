import pandas as pd

from src.data_ingestion.free_equity_enrichment import (
    FUNDAMENTALS_SOURCE,
    build_reference_row,
    enrich_reference_row,
    parse_annual_fundamentals,
)


def test_reference_row_converts_pence_liquidity_and_percent_yield():
    row = build_reference_row(
        {
            "security_id": "SHEL.LSE",
            "provider_symbol": "SHEL.L",
            "company_name": "Shell",
            "trading_currency": "GBX",
        },
        {
            "symbol": "SHEL.L",
            "currency": "GBp",
            "financialCurrency": "USD",
            "regularMarketPrice": 2500,
            "marketCap": 1000,
            "averageDailyVolume3Month": 10,
            "dividendYield": 4.0,
        },
        {"GBP": 0.8, "USD": 1.0},
        retrieved_at=pd.Timestamp("2026-08-07 08:00:00"),
        ingestion_run_id="run-1",
    )
    assert row["quote_currency"] == "GBP"
    assert row["price_scale"] == 0.01
    assert row["market_cap_usd"] == 1250
    assert row["average_daily_value_usd"] == 312.5
    assert row["dividend_yield"] == 0.04


def test_profile_enrichment_maps_sector_and_nested_values():
    base = build_reference_row(
        {
            "security_id": "ABC.US",
            "provider_symbol": "ABC",
            "company_name": "ABC",
            "trading_currency": "USD",
        },
        {
            "currency": "USD",
            "regularMarketPrice": 10,
            "marketCap": 1000,
            "averageDailyVolume3Month": 100,
        },
        {"USD": 1.0},
        retrieved_at=pd.Timestamp("2026-08-07 08:00:00"),
        ingestion_run_id="run-1",
    )
    enriched = enrich_reference_row(
        base,
        {
            "assetProfile": {
                "sector": "Consumer Defensive",
                "industry": "Household Products",
            },
            "financialData": {
                "returnOnEquity": {"raw": 0.20},
                "freeCashflow": {"raw": 50},
            },
            "defaultKeyStatistics": {
                "payoutRatio": {"raw": 0.45},
            },
        },
        {"USD": 1.0},
    )
    assert enriched["sector"] == "Consumer Staples"
    assert enriched["industry"] == "Household Products"
    assert enriched["return_on_equity"] == 0.20
    assert enriched["free_cash_flow"] == 50
    assert enriched["payout_ratio"] == 0.45


def test_annual_statement_parser_builds_reported_period_rows():
    payload = [
        {
            "annualTotalRevenue": [
                {
                    "asOfDate": "2024-12-31",
                    "currencyCode": "USD",
                    "reportedValue": {"raw": 100},
                },
                {
                    "asOfDate": "2025-12-31",
                    "currencyCode": "USD",
                    "reportedValue": {"raw": 120},
                },
            ]
        },
        {
            "annualFreeCashFlow": [
                {
                    "asOfDate": "2024-12-31",
                    "currencyCode": "USD",
                    "reportedValue": {"raw": 10},
                },
                {
                    "asOfDate": "2025-12-31",
                    "currencyCode": "USD",
                    "reportedValue": {"raw": 15},
                },
            ]
        },
    ]
    frame = parse_annual_fundamentals(
        "ABC.US",
        payload,
        retrieved_at=pd.Timestamp("2026-08-07 08:00:00"),
        ingestion_run_id="run-1",
    )
    assert len(frame) == 2
    assert set(frame["revenue"]) == {100.0, 120.0}
    assert set(frame["free_cash_flow"]) == {10.0, 15.0}
    assert frame["source"].eq(FUNDAMENTALS_SOURCE).all()
    assert frame["available_from"].eq(pd.Timestamp("2026-08-07 08:00:00")).all()
