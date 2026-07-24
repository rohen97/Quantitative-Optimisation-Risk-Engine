CREATE OR REPLACE VIEW point_in_time_fx AS
SELECT *
FROM fx_rates
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY base_currency, quote_currency, rate_date
    ORDER BY retrieved_at DESC
) = 1;
