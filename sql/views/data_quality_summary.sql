CREATE OR REPLACE VIEW data_quality_summary AS
SELECT 'prices_daily' AS table_name, COUNT(*) AS row_count, COUNT(DISTINCT security_id) AS entity_count FROM prices_daily
UNION ALL
SELECT 'fundamentals_reported', COUNT(*), COUNT(DISTINCT security_id) FROM fundamentals_reported
UNION ALL
SELECT 'macro_observations', COUNT(*), COUNT(DISTINCT series_id) FROM macro_observations
UNION ALL
SELECT 'fx_rates', COUNT(*), COUNT(DISTINCT base_currency || '/' || quote_currency) FROM fx_rates;
