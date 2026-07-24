CREATE OR REPLACE VIEW point_in_time_fundamentals AS
WITH ranked AS (
    SELECT
        d.security_id,
        d.as_of_date,
        f.fiscal_period_end,
        f.fiscal_period_type,
        f.filing_date,
        f.available_from,
        f.currency,
        f.revenue,
        f.operating_income,
        f.net_income,
        f.operating_cash_flow,
        f.capital_expenditure,
        f.free_cash_flow,
        f.total_assets,
        f.total_liabilities,
        f.total_debt,
        f.cash_and_equivalents,
        f.shareholders_equity,
        f.dividends_paid,
        f.diluted_shares,
        f.source,
        f.vintage_id,
        ROW_NUMBER() OVER (
            PARTITION BY
                d.security_id,
                d.as_of_date,
                f.fiscal_period_type
            ORDER BY
                f.available_from DESC,
                f.retrieved_at DESC
        ) AS row_number
    FROM decision_dates AS d
    LEFT JOIN fundamentals_reported AS f
        ON f.security_id = d.security_id
       AND f.available_from <= CAST(d.as_of_date AS TIMESTAMP)
)
SELECT *
EXCLUDE (row_number)
FROM ranked
WHERE row_number = 1;
