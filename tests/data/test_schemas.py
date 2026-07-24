from src.data.schemas import SCHEMAS, schema_names


def test_required_data_schemas_exist_with_primary_keys():
    required = {
        "data_ingestion_runs",
        "raw_payload_metadata",
        "securities",
        "security_identifiers",
        "prices_daily",
        "fundamentals_reported",
        "macro_observations",
        "fx_rates",
        "news_documents",
        "news_security_map",
        "feature_snapshots_monthly",
        "portfolio_weight_snapshots",
        "model_metric_snapshots",
        "model_runs",
        "model_outputs",
    }
    assert required.issubset(set(schema_names()))
    for name in required:
        assert SCHEMAS[name].primary_key
        assert SCHEMAS[name].column_names
