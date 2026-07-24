CREATE INDEX IF NOT EXISTS idx_prices_security_date ON prices_daily (security_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_fundamentals_security_available ON fundamentals_reported (security_id, available_from);
CREATE INDEX IF NOT EXISTS idx_macro_series_vintage ON macro_observations (series_id, observation_date, vintage_date);
CREATE INDEX IF NOT EXISTS idx_fx_pair_date ON fx_rates (base_currency, quote_currency, rate_date);
CREATE INDEX IF NOT EXISTS idx_model_outputs_run ON model_outputs (model_run_id, output_name);
