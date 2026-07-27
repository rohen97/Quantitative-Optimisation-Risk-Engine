CREATE TABLE IF NOT EXISTS production_runs (
    production_run_id VARCHAR PRIMARY KEY,
    schedule_mode VARCHAR NOT NULL,
    validation_mode VARCHAR NOT NULL,
    as_of_date TIMESTAMP NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status VARCHAR NOT NULL,
    approval_status VARCHAR,
    backend VARCHAR NOT NULL,
    host_name VARCHAR,
    process_id BIGINT,
    git_commit_hash VARCHAR,
    git_is_dirty BOOLEAN,
    config_hash VARCHAR NOT NULL,
    input_snapshot_hash VARCHAR,
    model_run_id VARCHAR,
    ic_report_run_id VARCHAR,
    validation_run_id VARCHAR,
    output_directory VARCHAR,
    log_path VARCHAR,
    exit_code INTEGER,
    error_type VARCHAR,
    error_message VARCHAR
);

CREATE TABLE IF NOT EXISTS production_step_runs (
    production_run_id VARCHAR NOT NULL,
    step_name VARCHAR NOT NULL,
    step_order INTEGER NOT NULL,
    required BOOLEAN NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status VARCHAR NOT NULL,
    attempt_count INTEGER NOT NULL,
    duration_seconds DOUBLE,
    command_json JSON,
    exit_code INTEGER,
    stdout_path VARCHAR,
    stderr_path VARCHAR,
    error_message VARCHAR,
    PRIMARY KEY (production_run_id, step_name)
);

CREATE TABLE IF NOT EXISTS production_alerts (
    alert_id VARCHAR PRIMARY KEY,
    production_run_id VARCHAR,
    created_at TIMESTAMP NOT NULL,
    severity VARCHAR NOT NULL,
    component VARCHAR NOT NULL,
    alert_type VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    message VARCHAR NOT NULL,
    fingerprint VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    deduplicated BOOLEAN NOT NULL,
    delivery_channels_json JSON,
    delivery_results_json JSON,
    resolved_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS production_incidents (
    incident_id VARCHAR PRIMARY KEY,
    fingerprint VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    component VARCHAR NOT NULL,
    severity VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    opened_at TIMESTAMP NOT NULL,
    last_seen_at TIMESTAMP NOT NULL,
    resolved_at TIMESTAMP,
    first_production_run_id VARCHAR,
    latest_production_run_id VARCHAR,
    occurrence_count INTEGER NOT NULL,
    resolution_note VARCHAR
);

CREATE TABLE IF NOT EXISTS production_health_checks (
    production_run_id VARCHAR NOT NULL,
    check_name VARCHAR NOT NULL,
    checked_at TIMESTAMP NOT NULL,
    status VARCHAR NOT NULL,
    severity VARCHAR NOT NULL,
    metric_value DOUBLE,
    metric_text VARCHAR,
    threshold_value DOUBLE,
    message VARCHAR,
    PRIMARY KEY (production_run_id, check_name)
);

CREATE TABLE IF NOT EXISTS production_drift_checks (
    production_run_id VARCHAR NOT NULL,
    drift_type VARCHAR NOT NULL,
    segment VARCHAR NOT NULL,
    metric_name VARCHAR NOT NULL,
    metric_value DOUBLE,
    warning_threshold DOUBLE,
    critical_threshold DOUBLE,
    status VARCHAR NOT NULL,
    sample_size INTEGER,
    notes VARCHAR,
    PRIMARY KEY (production_run_id, drift_type, segment, metric_name)
);

CREATE TABLE IF NOT EXISTS production_heartbeats (
    service_name VARCHAR PRIMARY KEY,
    last_heartbeat_at TIMESTAMP NOT NULL,
    status VARCHAR NOT NULL,
    production_run_id VARCHAR,
    details_json JSON
);
