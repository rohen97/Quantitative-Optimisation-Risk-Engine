CREATE TABLE IF NOT EXISTS security_price_summaries (
    security_id VARCHAR PRIMARY KEY,
    price_rows BIGINT NOT NULL,
    latest_trade_date DATE NOT NULL,
    avg_daily_traded_value_local DOUBLE,
    observed_volume_rows BIGINT NOT NULL,
    latest_source_retrieved_at TIMESTAMP NOT NULL,
    refreshed_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS model_input_summary_state (
    dataset_name VARCHAR PRIMARY KEY,
    source_row_count BIGINT NOT NULL,
    source_max_retrieved_at TIMESTAMP,
    summary_row_count BIGINT NOT NULL,
    status VARCHAR NOT NULL,
    refreshed_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_security_price_summary_latest
ON security_price_summaries (latest_trade_date, price_rows);
