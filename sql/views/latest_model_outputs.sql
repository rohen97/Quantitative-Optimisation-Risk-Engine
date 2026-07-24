CREATE OR REPLACE VIEW latest_model_outputs AS
SELECT outputs.*
FROM model_outputs AS outputs
JOIN model_runs AS runs
    ON outputs.model_run_id = runs.model_run_id
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY outputs.output_name, outputs.ticker, outputs.metric
    ORDER BY runs.as_of_date DESC, runs.started_at DESC
) = 1;
