CREATE OR REPLACE VIEW point_in_time_prices AS
SELECT
    security_id,
    security_id AS ticker,
    trade_date AS date,
    open_price,
    high_price,
    low_price,
    close_price AS close,
    adjusted_close,
    volume,
    trading_currency,
    source,
    retrieved_at,
    ingestion_run_id,
    row_hash,
    adjusted_close / NULLIF(
        LAG(adjusted_close) OVER (
            PARTITION BY security_id
            ORDER BY trade_date
        ),
        0
    ) - 1 AS return
FROM prices_daily
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY security_id, trade_date
    ORDER BY retrieved_at DESC
) = 1;
