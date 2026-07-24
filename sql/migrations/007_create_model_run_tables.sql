CREATE TABLE IF NOT EXISTS model_runs (
    model_run_id VARCHAR PRIMARY KEY,
    model_name VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    git_commit_hash VARCHAR,
    git_is_dirty BOOLEAN,
    backend VARCHAR NOT NULL,
    mode VARCHAR NOT NULL,
    as_of_date TIMESTAMP NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status VARCHAR NOT NULL,
    config_hash VARCHAR NOT NULL,
    input_snapshot_hash VARCHAR,
    random_seed INTEGER,
    train_start DATE,
    train_end DATE,
    validation_start DATE,
    validation_end DATE,
    test_start DATE,
    test_end DATE,
    output_path VARCHAR,
    error_message VARCHAR,
    runtime_seconds DOUBLE
);

CREATE TABLE IF NOT EXISTS model_outputs (
    model_run_id VARCHAR NOT NULL,
    output_name VARCHAR NOT NULL,
    ticker VARCHAR,
    metric VARCHAR,
    value DOUBLE,
    payload_json VARCHAR,
    PRIMARY KEY (model_run_id, output_name, ticker, metric)
);

ALTER TABLE model_runs ADD COLUMN IF NOT EXISTS runtime_seconds DOUBLE;
