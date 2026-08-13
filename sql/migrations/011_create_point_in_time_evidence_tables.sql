CREATE TABLE IF NOT EXISTS filing_metadata (
    security_id VARCHAR NOT NULL,
    entity_cik VARCHAR NOT NULL,
    accession_number VARCHAR NOT NULL,
    form_type VARCHAR NOT NULL,
    report_date DATE,
    filing_date DATE,
    acceptance_datetime TIMESTAMP,
    filing_index_url VARCHAR,
    source VARCHAR NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    ingestion_run_id VARCHAR,
    row_hash VARCHAR NOT NULL,
    PRIMARY KEY (entity_cik, accession_number, source)
);

CREATE TABLE IF NOT EXISTS security_reference_events (
    event_id VARCHAR NOT NULL,
    security_id VARCHAR NOT NULL,
    provider_symbol VARCHAR NOT NULL,
    exchange_code VARCHAR,
    event_type VARCHAR NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    old_symbol VARCHAR,
    new_symbol VARCHAR,
    index_symbol VARCHAR,
    is_delisted BOOLEAN,
    source VARCHAR NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    ingestion_run_id VARCHAR,
    row_hash VARCHAR NOT NULL,
    PRIMARY KEY (event_id)
);

CREATE INDEX IF NOT EXISTS idx_filing_metadata_security_report
    ON filing_metadata (security_id, report_date, acceptance_datetime);
CREATE INDEX IF NOT EXISTS idx_reference_events_security_dates
    ON security_reference_events (security_id, effective_from, effective_to);
CREATE INDEX IF NOT EXISTS idx_reference_events_type_dates
    ON security_reference_events (event_type, effective_from, effective_to);
