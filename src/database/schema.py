TABLES = [
    "securities_master",
    "prices_daily",
    "fundamentals_quarterly",
    "dividends",
    "corporate_actions",
    "current_holdings",
    "features_monthly",
    "alt_text_documents",
    "alt_entity_mentions",
    "alt_sentiment_scores",
    "alt_event_signals",
    "alt_features_monthly",
    "market_regimes",
    "model_recommendations",
    "portfolio_runs",
    "stress_test_results",
    "hedge_recommendations",
]


def sqlite_schema() -> str:
    return "\n".join(f"CREATE TABLE IF NOT EXISTS {table} (id INTEGER PRIMARY KEY);" for table in TABLES)
