CREATE OR REPLACE VIEW point_in_time_macro AS
WITH ranked AS (
    SELECT
        d.as_of_date,
        m.series_id,
        m.observation_date,
        m.vintage_date,
        m.available_from,
        m.value,
        m.unit,
        m.source,
        ROW_NUMBER() OVER (
            PARTITION BY
                d.as_of_date,
                m.series_id,
                m.observation_date
            ORDER BY
                m.vintage_date DESC,
                m.retrieved_at DESC
        ) AS row_number
    FROM model_decision_dates AS d
    JOIN macro_observations AS m
        ON m.available_from <= CAST(d.as_of_date AS TIMESTAMP)
)
SELECT *
EXCLUDE (row_number)
FROM ranked
WHERE row_number = 1;
