CREATE TABLE IF NOT EXISTS fundamental_vintages (
    security_id VARCHAR NOT NULL,
    provider_symbol VARCHAR NOT NULL,
    fiscal_period_end DATE NOT NULL,
    fiscal_period_type VARCHAR NOT NULL,
    available_from TIMESTAMP NOT NULL,
    announcement_at TIMESTAMP,
    revision_at TIMESTAMP,
    currency VARCHAR,
    revenue DOUBLE,
    operating_income DOUBLE,
    net_income DOUBLE,
    operating_cash_flow DOUBLE,
    capital_expenditure DOUBLE,
    free_cash_flow DOUBLE,
    total_assets DOUBLE,
    total_liabilities DOUBLE,
    total_debt DOUBLE,
    cash_and_equivalents DOUBLE,
    shareholders_equity DOUBLE,
    dividends_paid DOUBLE,
    diluted_shares DOUBLE,
    ebitda DOUBLE,
    interest_expense DOUBLE,
    source VARCHAR NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    ingestion_run_id VARCHAR,
    vintage_id VARCHAR NOT NULL,
    vintage_semantics VARCHAR NOT NULL,
    row_hash VARCHAR NOT NULL,
    PRIMARY KEY (
        security_id,
        fiscal_period_end,
        fiscal_period_type,
        source,
        vintage_id
    )
);

CREATE TABLE IF NOT EXISTS corporate_action_vintages (
    event_id VARCHAR NOT NULL,
    vintage_id VARCHAR NOT NULL,
    security_id VARCHAR NOT NULL,
    provider_symbol VARCHAR NOT NULL,
    action_type VARCHAR NOT NULL,
    declaration_date DATE,
    ex_date DATE NOT NULL,
    record_date DATE,
    payment_date DATE,
    effective_date DATE,
    split_ratio DOUBLE,
    cash_amount DOUBLE,
    currency VARCHAR,
    available_from TIMESTAMP NOT NULL,
    revision_at TIMESTAMP,
    source VARCHAR NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    ingestion_run_id VARCHAR,
    row_hash VARCHAR NOT NULL,
    PRIMARY KEY (event_id, vintage_id)
);

CREATE TABLE IF NOT EXISTS market_cap_vintages (
    security_id VARCHAR NOT NULL,
    provider_symbol VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    available_from TIMESTAMP NOT NULL,
    market_cap_local DOUBLE,
    shares_outstanding DOUBLE,
    free_float_shares DOUBLE,
    free_float_percent DOUBLE,
    free_float_market_cap_local DOUBLE,
    currency VARCHAR,
    source VARCHAR NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    ingestion_run_id VARCHAR,
    vintage_id VARCHAR NOT NULL,
    row_hash VARCHAR NOT NULL,
    PRIMARY KEY (security_id, as_of_date, source, vintage_id)
);

CREATE TABLE IF NOT EXISTS identifier_vintages (
    security_id VARCHAR NOT NULL,
    identifier_type VARCHAR NOT NULL,
    identifier_value VARCHAR NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    available_from TIMESTAMP NOT NULL,
    provider_symbol VARCHAR,
    source VARCHAR NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    ingestion_run_id VARCHAR,
    vintage_id VARCHAR NOT NULL,
    row_hash VARCHAR NOT NULL,
    PRIMARY KEY (
        security_id,
        identifier_type,
        identifier_value,
        effective_from,
        source,
        vintage_id
    )
);

CREATE TABLE IF NOT EXISTS macro_release_vintages (
    series_id VARCHAR NOT NULL,
    observation_date DATE NOT NULL,
    release_at TIMESTAMP NOT NULL,
    revision_at TIMESTAMP NOT NULL,
    available_from TIMESTAMP NOT NULL,
    value DOUBLE,
    unit VARCHAR,
    frequency VARCHAR,
    source VARCHAR NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    ingestion_run_id VARCHAR,
    vintage_id VARCHAR NOT NULL,
    row_hash VARCHAR NOT NULL,
    PRIMARY KEY (series_id, observation_date, source, vintage_id)
);

CREATE TABLE IF NOT EXISTS sentiment_vintages (
    document_id VARCHAR NOT NULL,
    security_id VARCHAR NOT NULL,
    published_at TIMESTAMP NOT NULL,
    available_from TIMESTAMP NOT NULL,
    source_name VARCHAR NOT NULL,
    sentiment_score DOUBLE,
    sentiment_label VARCHAR,
    model_version VARCHAR NOT NULL,
    entity_mapping_version VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    ingestion_run_id VARCHAR,
    vintage_id VARCHAR NOT NULL,
    row_hash VARCHAR NOT NULL,
    PRIMARY KEY (document_id, security_id, model_version, vintage_id)
);

CREATE TABLE IF NOT EXISTS decision_snapshot_manifests (
    model_run_id VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    model_name VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    git_commit_hash VARCHAR,
    eligible_universe_hash VARCHAR NOT NULL,
    feature_snapshot_hash VARCHAR NOT NULL,
    forecast_snapshot_hash VARCHAR NOT NULL,
    ranking_snapshot_hash VARCHAR NOT NULL,
    portfolio_snapshot_hash VARCHAR NOT NULL,
    config_hash VARCHAR NOT NULL,
    archive_path VARCHAR,
    available_from TIMESTAMP NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    source VARCHAR NOT NULL,
    PRIMARY KEY (model_run_id, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_fundamental_vintages_pit
    ON fundamental_vintages (security_id, available_from, fiscal_period_end);
CREATE INDEX IF NOT EXISTS idx_corporate_action_vintages_pit
    ON corporate_action_vintages (security_id, available_from, ex_date);
CREATE INDEX IF NOT EXISTS idx_market_cap_vintages_pit
    ON market_cap_vintages (security_id, available_from, as_of_date);
CREATE INDEX IF NOT EXISTS idx_identifier_vintages_pit
    ON identifier_vintages (security_id, available_from, effective_from, effective_to);
CREATE INDEX IF NOT EXISTS idx_macro_release_vintages_pit
    ON macro_release_vintages (series_id, available_from, observation_date);
CREATE INDEX IF NOT EXISTS idx_sentiment_vintages_pit
    ON sentiment_vintages (security_id, available_from, published_at);
