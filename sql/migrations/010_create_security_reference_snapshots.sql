CREATE TABLE IF NOT EXISTS security_reference_snapshots (
    security_id VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    provider_symbol VARCHAR NOT NULL,
    company_name VARCHAR,
    sector VARCHAR,
    industry VARCHAR,
    quote_currency VARCHAR,
    financial_currency VARCHAR,
    regular_market_price DOUBLE,
    price_scale DOUBLE,
    market_cap_local DOUBLE,
    market_cap_usd DOUBLE,
    shares_outstanding DOUBLE,
    average_daily_volume_3m DOUBLE,
    average_daily_value_usd DOUBLE,
    dividend_yield DOUBLE,
    trailing_pe DOUBLE,
    price_to_book DOUBLE,
    enterprise_value_local DOUBLE,
    enterprise_value_usd DOUBLE,
    enterprise_to_ebitda DOUBLE,
    payout_ratio DOUBLE,
    return_on_equity DOUBLE,
    return_on_assets DOUBLE,
    total_cash DOUBLE,
    total_debt DOUBLE,
    ebitda DOUBLE,
    free_cash_flow DOUBLE,
    operating_cash_flow DOUBLE,
    source VARCHAR NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    ingestion_run_id VARCHAR,
    row_hash VARCHAR NOT NULL,
    PRIMARY KEY (security_id, as_of_date, source)
);

ALTER TABLE fundamentals_reported ADD COLUMN IF NOT EXISTS ebitda DOUBLE;
ALTER TABLE fundamentals_reported ADD COLUMN IF NOT EXISTS interest_expense DOUBLE;

CREATE INDEX IF NOT EXISTS idx_security_reference_latest
    ON security_reference_snapshots (security_id, as_of_date);
CREATE INDEX IF NOT EXISTS idx_security_reference_region_fields
    ON security_reference_snapshots (market_cap_usd, average_daily_value_usd);
