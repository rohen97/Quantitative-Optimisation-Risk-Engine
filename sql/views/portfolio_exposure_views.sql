CREATE OR REPLACE VIEW portfolio_exposure_views AS
SELECT
    model_run_id,
    output_name,
    ticker,
    metric,
    value
FROM model_outputs
WHERE output_name LIKE '%exposure%';
