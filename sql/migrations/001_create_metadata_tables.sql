CREATE TABLE IF NOT EXISTS data_ingestion_runs (
    ingestion_run_id VARCHAR PRIMARY KEY,
    source_name VARCHAR NOT NULL,
    dataset_name VARCHAR NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status VARCHAR NOT NULL,
    requested_start_date DATE,
    requested_end_date DATE,
    request_parameters_json JSON,
    row_count BIGINT,
    inserted_count BIGINT,
    updated_count BIGINT,
    rejected_count BIGINT,
    payload_hash VARCHAR,
    config_hash VARCHAR,
    error_message VARCHAR
);

CREATE TABLE IF NOT EXISTS raw_payload_metadata (
    payload_id VARCHAR PRIMARY KEY,
    ingestion_run_id VARCHAR NOT NULL,
    source_name VARCHAR NOT NULL,
    dataset_name VARCHAR NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    request_parameters_json JSON,
    response_status INTEGER,
    payload_hash VARCHAR NOT NULL,
    archive_path VARCHAR,
    row_count BIGINT,
    FOREIGN KEY (ingestion_run_id)
        REFERENCES data_ingestion_runs(ingestion_run_id)
);

CREATE TABLE IF NOT EXISTS securities (
    security_id VARCHAR PRIMARY KEY,
    company_name VARCHAR NOT NULL,
    instrument_type VARCHAR NOT NULL,
    listing_status VARCHAR NOT NULL,
    exchange_code VARCHAR,
    country VARCHAR,
    region VARCHAR,
    sector VARCHAR,
    industry VARCHAR,
    trading_currency VARCHAR,
    domicile_currency VARCHAR,
    first_seen_at TIMESTAMP NOT NULL,
    last_seen_at TIMESTAMP NOT NULL,
    source VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS security_identifiers (
    security_id VARCHAR NOT NULL,
    identifier_type VARCHAR NOT NULL,
    identifier_value VARCHAR NOT NULL,
    valid_from DATE,
    valid_to DATE,
    source VARCHAR NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    PRIMARY KEY (
        security_id,
        identifier_type,
        identifier_value,
        valid_from
    )
);

CREATE TABLE IF NOT EXISTS data_lineage (
    lineage_id TEXT PRIMARY KEY,
    table_name TEXT NOT NULL,
    source TEXT NOT NULL,
    source_uri TEXT,
    payload_hash TEXT,
    ingested_at TIMESTAMP NOT NULL
);
