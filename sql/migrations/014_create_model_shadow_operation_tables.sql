CREATE TABLE IF NOT EXISTS model_shadow_cycles (
    cycle_id VARCHAR NOT NULL PRIMARY KEY,
    as_of_date DATE NOT NULL,
    recorded_at TIMESTAMP NOT NULL,
    production_run_id VARCHAR,
    model_version VARCHAR NOT NULL,
    selected_source VARCHAR NOT NULL,
    governance_status VARCHAR NOT NULL,
    selected_portfolio_hash VARCHAR NOT NULL,
    portfolio_bundle_hash VARCHAR,
    evaluation_due_date DATE NOT NULL,
    evaluation_status VARCHAR NOT NULL,
    prospective_eligible BOOLEAN NOT NULL,
    prior_cycle_id VARCHAR,
    selected_weight_l1_change DOUBLE,
    selected_name_overlap DOUBLE,
    estimated_turnover DOUBLE,
    estimated_cost_fraction DOUBLE,
    evaluated_at TIMESTAMP,
    active_return_vs_equal_weight DOUBLE,
    realised_slippage_bps DOUBLE,
    notes VARCHAR
);

ALTER TABLE model_shadow_cycles
ADD COLUMN IF NOT EXISTS portfolio_bundle_hash VARCHAR;

CREATE TABLE IF NOT EXISTS model_shadow_cycle_weights (
    cycle_id VARCHAR NOT NULL,
    portfolio_name VARCHAR NOT NULL,
    security_id VARCHAR NOT NULL,
    target_weight DOUBLE NOT NULL,
    decision_trade_date DATE,
    decision_price DOUBLE,
    currency VARCHAR,
    PRIMARY KEY (cycle_id, portfolio_name, security_id)
);

CREATE TABLE IF NOT EXISTS model_shadow_cycle_results (
    cycle_id VARCHAR NOT NULL,
    portfolio_name VARCHAR NOT NULL,
    evaluated_at TIMESTAMP NOT NULL,
    gross_return DOUBLE,
    net_return DOUBLE,
    estimated_turnover DOUBLE,
    estimated_cost_fraction DOUBLE,
    valid_weight DOUBLE NOT NULL,
    missing_security_count INTEGER NOT NULL,
    status VARCHAR NOT NULL,
    PRIMARY KEY (cycle_id, portfolio_name)
);
