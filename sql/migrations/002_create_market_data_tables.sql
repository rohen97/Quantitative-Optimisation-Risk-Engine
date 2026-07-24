CREATE TABLE IF NOT EXISTS prices_daily (
    security_id VARCHAR NOT NULL,
    trade_date DATE NOT NULL,
    open_price DOUBLE,
    high_price DOUBLE,
    low_price DOUBLE,
    close_price DOUBLE,
    adjusted_close DOUBLE,
    volume DOUBLE,
    trading_currency VARCHAR,
    source VARCHAR NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    ingestion_run_id VARCHAR,
    row_hash VARCHAR NOT NULL,
    PRIMARY KEY (
        security_id,
        trade_date,
        source
    )
);

CREATE TABLE IF NOT EXISTS corporate_actions (
    security_id VARCHAR NOT NULL,
    action_type VARCHAR NOT NULL,
    ex_date DATE NOT NULL,
    effective_date DATE,
    split_ratio DOUBLE,
    cash_amount DOUBLE,
    currency VARCHAR,
    source VARCHAR NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    ingestion_run_id VARCHAR,
    PRIMARY KEY (
        security_id,
        action_type,
        ex_date,
        source
    )
);

CREATE TABLE IF NOT EXISTS dividends (
    security_id VARCHAR NOT NULL,
    declaration_date DATE,
    ex_dividend_date DATE NOT NULL,
    record_date DATE,
    payment_date DATE,
    dividend_amount DOUBLE NOT NULL,
    currency VARCHAR,
    dividend_type VARCHAR,
    available_from TIMESTAMP NOT NULL,
    source VARCHAR NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    ingestion_run_id VARCHAR,
    PRIMARY KEY (
        security_id,
        ex_dividend_date,
        dividend_type,
        source
    )
);
