TABLES = {
    "securities_master": """
        CREATE TABLE IF NOT EXISTS securities_master (
            security_id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL UNIQUE,
            company_name TEXT NOT NULL,
            country TEXT,
            region TEXT,
            currency TEXT,
            sector TEXT,
            exchange TEXT,
            is_active INTEGER DEFAULT 1
        );
    """,
    "prices_daily": """
        CREATE TABLE IF NOT EXISTS prices_daily (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL NOT NULL,
            volume REAL,
            return REAL,
            data_vendor TEXT,
            PRIMARY KEY (ticker, date)
        );
    """,
    "fundamentals_quarterly": """
        CREATE TABLE IF NOT EXISTS fundamentals_quarterly (
            ticker TEXT NOT NULL,
            fiscal_period TEXT NOT NULL,
            filing_date TEXT,
            revenue REAL,
            ebitda REAL,
            net_income REAL,
            free_cash_flow REAL,
            total_debt REAL,
            cash REAL,
            shareholders_equity REAL,
            data_vendor TEXT,
            PRIMARY KEY (ticker, fiscal_period)
        );
    """,
    "dividends": """
        CREATE TABLE IF NOT EXISTS dividends (
            ticker TEXT NOT NULL,
            ex_date TEXT NOT NULL,
            pay_date TEXT,
            dividend_per_share REAL NOT NULL,
            currency TEXT,
            dividend_type TEXT,
            data_vendor TEXT,
            PRIMARY KEY (ticker, ex_date)
        );
    """,
    "current_holdings": """
        CREATE TABLE IF NOT EXISTS current_holdings (
            run_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            company_name TEXT NOT NULL,
            country TEXT,
            region TEXT,
            currency TEXT,
            sector TEXT,
            shares REAL NOT NULL,
            current_price REAL NOT NULL,
            market_value_usd REAL NOT NULL,
            dividend_yield REAL NOT NULL,
            beta REAL NOT NULL,
            volatility REAL NOT NULL,
            weight REAL,
            dividend_income_usd REAL,
            PRIMARY KEY (run_id, ticker)
        );
    """,
    "features_monthly": """
        CREATE TABLE IF NOT EXISTS features_monthly (
            ticker TEXT NOT NULL,
            feature_month TEXT NOT NULL,
            feature_name TEXT NOT NULL,
            feature_value REAL,
            data_vendor TEXT,
            PRIMARY KEY (ticker, feature_month, feature_name)
        );
    """,
    "model_recommendations": """
        CREATE TABLE IF NOT EXISTS model_recommendations (
            run_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            horizon_months INTEGER NOT NULL,
            recommendation TEXT,
            target_weight REAL,
            expected_total_return REAL,
            risk_adjusted_return REAL,
            var_5 REAL,
            cvar_5 REAL,
            p5_return REAL,
            p50_return REAL,
            p95_return REAL,
            final_recommendation_score REAL,
            risk_management_flags TEXT,
            PRIMARY KEY (run_id, ticker, horizon_months)
        );
    """,
    "portfolio_runs": """
        CREATE TABLE IF NOT EXISTS portfolio_runs (
            run_id TEXT PRIMARY KEY,
            run_timestamp TEXT NOT NULL,
            config_path TEXT,
            current_portfolio_path TEXT,
            total_nav_usd REAL,
            notes TEXT
        );
    """,
    "stress_test_results": """
        CREATE TABLE IF NOT EXISTS stress_test_results (
            run_id TEXT NOT NULL,
            scenario TEXT NOT NULL,
            portfolio_loss_usd REAL,
            portfolio_loss_pct REAL,
            worst_contributing_stock TEXT,
            residual_risk TEXT,
            PRIMARY KEY (run_id, scenario)
        );
    """,
    "hedge_recommendations": """
        CREATE TABLE IF NOT EXISTS hedge_recommendations (
            run_id TEXT NOT NULL,
            risk_exposure TEXT NOT NULL,
            hedge_type TEXT NOT NULL,
            hedge_instrument_or_basket TEXT,
            target_weight REAL,
            expected_hedge_effectiveness TEXT,
            trade_off_cost TEXT,
            residual_risk TEXT
        );
    """,
}


def sqlite_schema() -> str:
    """Return vendor-agnostic local SQLite DDL for the MVP tables."""
    return "\n".join(TABLES.values())
