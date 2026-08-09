from __future__ import annotations

from uuid import uuid4

import pandas as pd


def build_feature_snapshot(features: pd.DataFrame, as_of_date: str | pd.Timestamp, source_backend: str) -> tuple[str, pd.DataFrame]:
    model_run_id = str(uuid4())
    data = features.copy()
    id_column = "security_id" if "security_id" in data else "ticker" if "ticker" in data else data.columns[0]
    value_columns = [column for column in data.columns if column != id_column]
    long = data.melt(id_vars=[id_column], value_vars=value_columns, var_name="feature_name", value_name="feature_value")
    long = long.rename(columns={id_column: "security_id"})
    long["model_run_id"] = model_run_id
    long["security_id"] = long["security_id"].astype(str).str.upper()
    long["as_of_date"] = pd.Timestamp(as_of_date).normalize()
    long["feature_value"] = pd.to_numeric(long["feature_value"], errors="coerce")
    long["feature_text_value"] = None
    long = long.dropna(subset=["feature_value"])
    long["feature_version"] = source_backend
    long["calculated_at"] = pd.Timestamp.now('UTC').tz_localize(None)
    return model_run_id, long[["model_run_id", "security_id", "as_of_date", "feature_name", "feature_value", "feature_text_value", "feature_version", "calculated_at"]]
