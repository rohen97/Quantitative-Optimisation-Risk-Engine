CREATE TABLE IF NOT EXISTS fx_rates (
    base_currency VARCHAR NOT NULL,
    quote_currency VARCHAR NOT NULL,
    rate_date DATE NOT NULL,
    rate DOUBLE NOT NULL,
    source VARCHAR NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    ingestion_run_id VARCHAR,
    PRIMARY KEY (
        base_currency,
        quote_currency,
        rate_date,
        source
    )
);

CREATE TABLE IF NOT EXISTS macro_observations (
    series_id VARCHAR NOT NULL,
    observation_date DATE NOT NULL,
    vintage_date DATE NOT NULL,
    available_from TIMESTAMP NOT NULL,
    value DOUBLE,
    unit VARCHAR,
    frequency VARCHAR,
    source VARCHAR NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    ingestion_run_id VARCHAR,
    PRIMARY KEY (
        series_id,
        observation_date,
        vintage_date,
        source
    )
);
