CREATE TABLE IF NOT EXISTS decision_dates (
    security_id VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    PRIMARY KEY (security_id, as_of_date)
);

CREATE TABLE IF NOT EXISTS model_decision_dates (
    as_of_date DATE NOT NULL PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS feature_snapshots_monthly (
    model_run_id VARCHAR NOT NULL,
    security_id VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    feature_name VARCHAR NOT NULL,
    feature_value DOUBLE,
    feature_text_value VARCHAR,
    feature_version VARCHAR NOT NULL,
    calculated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (
        model_run_id,
        security_id,
        as_of_date,
        feature_name
    )
);

CREATE TABLE IF NOT EXISTS portfolio_weight_snapshots (
    model_run_id VARCHAR NOT NULL,
    portfolio_name VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    security_id VARCHAR NOT NULL,
    weight DOUBLE NOT NULL,
    market_value_usd DOUBLE,
    recommendation VARCHAR,
    PRIMARY KEY (
        model_run_id,
        portfolio_name,
        as_of_date,
        security_id
    )
);

CREATE TABLE IF NOT EXISTS model_metric_snapshots (
    model_run_id VARCHAR NOT NULL,
    model_component VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    metric_name VARCHAR NOT NULL,
    metric_value DOUBLE,
    metric_text_value VARCHAR,
    PRIMARY KEY (
        model_run_id,
        model_component,
        as_of_date,
        metric_name
    )
);

CREATE TABLE IF NOT EXISTS regime_snapshots (
    model_run_id VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    regime_name VARCHAR NOT NULL,
    probability DOUBLE,
    source_backend VARCHAR,
    PRIMARY KEY (model_run_id, as_of_date, regime_name)
);

CREATE TABLE IF NOT EXISTS distributional_forecast_snapshots (
    model_run_id VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    security_id VARCHAR NOT NULL,
    horizon VARCHAR NOT NULL,
    metric_name VARCHAR NOT NULL,
    metric_value DOUBLE,
    PRIMARY KEY (model_run_id, as_of_date, security_id, horizon, metric_name)
);

CREATE TABLE IF NOT EXISTS scorecard_snapshots (
    model_run_id VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    security_id VARCHAR NOT NULL,
    score_name VARCHAR NOT NULL,
    score_value DOUBLE,
    PRIMARY KEY (model_run_id, as_of_date, security_id, score_name)
);

CREATE TABLE IF NOT EXISTS optimisation_snapshots (
    model_run_id VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    security_id VARCHAR NOT NULL,
    weight DOUBLE,
    objective VARCHAR,
    PRIMARY KEY (model_run_id, as_of_date, security_id)
);

CREATE TABLE IF NOT EXISTS risk_snapshots (
    model_run_id VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    security_id VARCHAR,
    risk_metric VARCHAR NOT NULL,
    value DOUBLE,
    PRIMARY KEY (model_run_id, as_of_date, security_id, risk_metric)
);

CREATE TABLE IF NOT EXISTS stress_test_snapshots (
    model_run_id VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    scenario_name VARCHAR NOT NULL,
    security_id VARCHAR,
    loss_estimate DOUBLE,
    PRIMARY KEY (model_run_id, as_of_date, scenario_name, security_id)
);

CREATE TABLE IF NOT EXISTS hedge_recommendation_snapshots (
    model_run_id VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    hedge_instrument VARCHAR NOT NULL,
    recommended_weight DOUBLE,
    reason VARCHAR,
    PRIMARY KEY (model_run_id, as_of_date, hedge_instrument)
);

CREATE TABLE IF NOT EXISTS drl_snapshots (
    model_run_id VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    security_id VARCHAR NOT NULL,
    raw_weight DOUBLE,
    projected_weight DOUBLE,
    accepted_weight DOUBLE,
    acceptance_status VARCHAR,
    PRIMARY KEY (model_run_id, as_of_date, security_id)
);

CREATE TABLE IF NOT EXISTS final_recommendation_snapshots (
    model_run_id VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    security_id VARCHAR NOT NULL,
    final_weight DOUBLE,
    selected_source VARCHAR,
    recommendation VARCHAR,
    PRIMARY KEY (model_run_id, as_of_date, security_id)
);
