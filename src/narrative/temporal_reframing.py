from __future__ import annotations

import pandas as pd


RISK_DISTANCE_COLUMNS = {
    "distress": "distance_from_distress_anchor",
    "dividend_risk": "distance_from_dividend_risk_anchor",
    "credit_stress": "distance_from_credit_stress_anchor",
    "governance_risk": "distance_from_governance_risk_anchor",
    "regulatory_overhang": "distance_from_regulatory_risk_anchor",
    "positive_quality": "distance_from_positive_quality_anchor",
}


def assign_narrative_state(row: pd.Series) -> str:
    """Assign a narrative state based on nearest anchor and drift."""
    closeness = {name: 1 - row[column] for name, column in RISK_DISTANCE_COLUMNS.items()}
    closest = max(closeness, key=closeness.get)
    if closest == "positive_quality" and row["semantic_drift_score"] < 35:
        return "positive_stable"
    if closest == "positive_quality":
        return "positive_improving"
    if closest == "distress":
        return "distress"
    if closest == "dividend_risk":
        return "dividend_risk"
    if closest == "credit_stress":
        return "credit_stress"
    if closest == "regulatory_overhang":
        return "regulatory_overhang"
    if closest == "governance_risk":
        return "governance_risk"
    if row["risk_reframing_score"] > 70:
        return "negative_deteriorating"
    return "neutral"


def analyse_temporal_reframing(distances: pd.DataFrame, as_of_date: pd.Timestamp | None = None) -> pd.DataFrame:
    """Aggregate semantic-distance behaviour over rolling windows."""
    if distances.empty:
        return pd.DataFrame()
    as_of = (as_of_date or pd.Timestamp.today()).normalize()
    data = distances.copy()
    data["publication_timestamp"] = pd.to_datetime(data["publication_timestamp"])
    data["narrative_state"] = data.apply(assign_narrative_state, axis=1)
    rows = []
    for (security_id, ticker), group in data.groupby(["security_id", "ticker"]):
        row = {"security_id": security_id, "ticker": ticker}
        for days in [7, 30, 90, 180]:
            window = group[group["publication_timestamp"] >= as_of - pd.Timedelta(days=days)]
            row[f"semantic_drift_{days}d"] = float(window["semantic_drift_score"].mean()) if not window.empty else 0.0
        row["narrative_instability_score"] = float(group["semantic_drift_score"].tail(5).mean())
        row["risk_reframing_score_30d"] = float(group[group["publication_timestamp"] >= as_of - pd.Timedelta(days=30)]["risk_reframing_score"].mean() or 0)
        row["risk_reframing_score_90d"] = float(group[group["publication_timestamp"] >= as_of - pd.Timedelta(days=90)]["risk_reframing_score"].mean() or 0)
        row["positive_reframing_score_30d"] = float(group[group["publication_timestamp"] >= as_of - pd.Timedelta(days=30)]["positive_reframing_score"].mean() or 0)
        row["positive_reframing_score_90d"] = float(group[group["publication_timestamp"] >= as_of - pd.Timedelta(days=90)]["positive_reframing_score"].mean() or 0)
        for state, column in RISK_DISTANCE_COLUMNS.items():
            if state == "positive_quality":
                continue
            output_state = "regulatory_risk" if state == "regulatory_overhang" else state
            row[f"{output_state}_similarity_score"] = float(((1 - group[column]).clip(0, 1) * 100).max())
        row["latest_narrative_state"] = group.sort_values("publication_timestamp").iloc[-1]["narrative_state"]
        rows.append(row)
    return pd.DataFrame(rows)
