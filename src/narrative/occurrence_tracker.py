from __future__ import annotations

import pandas as pd


def track_concept_occurrences(concepts: pd.DataFrame, as_of_date: pd.Timestamp | None = None) -> pd.DataFrame:
    """Track first appearances, reoccurrences and risk concept acceleration."""
    if concepts.empty:
        return concepts.copy()
    as_of = (as_of_date or pd.Timestamp.today()).normalize()
    data = concepts.copy()
    data["publication_timestamp"] = pd.to_datetime(data["publication_timestamp"])
    grouped = data.groupby(["security_id", "ticker", "concept_text"], as_index=False)
    summary = grouped.agg(
        first_appearance_date=("publication_timestamp", "min"),
        last_appearance_date=("publication_timestamp", "max"),
        concept_reoccurrence_count=("document_id", "count"),
        concept_polarity=("concept_polarity", "first"),
        concept_severity=("concept_severity", "max"),
    )
    for days in [7, 30, 90]:
        cutoff = as_of - pd.Timedelta(days=days)
        counts = data[data["publication_timestamp"] >= cutoff].groupby(["security_id", "concept_text"]).size()
        summary[f"concept_frequency_{days}d"] = [
            int(counts.get((row.security_id, row.concept_text), 0)) for row in summary.itertuples()
        ]
    previous_30 = data[(data["publication_timestamp"] < as_of - pd.Timedelta(days=30)) & (data["publication_timestamp"] >= as_of - pd.Timedelta(days=60))]
    previous_90 = data[(data["publication_timestamp"] < as_of - pd.Timedelta(days=90)) & (data["publication_timestamp"] >= as_of - pd.Timedelta(days=180))]
    prev30 = previous_30.groupby(["security_id", "concept_text"]).size()
    prev90 = previous_90.groupby(["security_id", "concept_text"]).size()
    summary["new_concept_flag"] = summary["first_appearance_date"] >= as_of - pd.Timedelta(days=30)
    summary["recurring_concept_flag"] = summary["concept_reoccurrence_count"] > 1
    summary["recurring_risk_flag"] = summary["recurring_concept_flag"] & summary["concept_polarity"].eq("negative") & (summary["concept_severity"] >= 70)
    summary["concept_acceleration_30d"] = [
        row.concept_frequency_30d - int(prev30.get((row.security_id, row.concept_text), 0)) for row in summary.itertuples()
    ]
    summary["concept_acceleration_90d"] = [
        row.concept_frequency_90d - int(prev90.get((row.security_id, row.concept_text), 0)) for row in summary.itertuples()
    ]
    return summary
