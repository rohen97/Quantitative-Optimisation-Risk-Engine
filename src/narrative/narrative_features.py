from __future__ import annotations

import pandas as pd


def build_narrative_reframing_features(
    occurrence_summary: pd.DataFrame,
    temporal_features: pd.DataFrame,
    markov_transitions: pd.DataFrame,
    as_of_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Aggregate concept, semantic and Markov outputs to company-level narrative features."""
    as_of = (as_of_date or pd.Timestamp.today()).normalize()
    if temporal_features.empty:
        return pd.DataFrame()
    concept_summary = occurrence_summary.groupby(["security_id", "ticker"], as_index=False).agg(
        new_risk_concept_count_30d=("new_concept_flag", lambda values: int(values.sum())),
        recurring_risk_concept_count_90d=("recurring_risk_flag", lambda values: int(values.sum())),
        concept_reoccurrence_intensity=("concept_reoccurrence_count", "sum"),
        concept_acceleration_score=("concept_acceleration_30d", lambda values: float(max(0, values.mean()) * 20)),
    )
    data = temporal_features.merge(concept_summary, on=["security_id", "ticker"], how="left").fillna(0)
    first_order = markov_transitions[markov_transitions["transition_order"] == 1] if not markov_transitions.empty else pd.DataFrame()

    def prob(from_state: str, to_state: str) -> pd.Series:
        if first_order.empty:
            return pd.Series(0, index=data.index)
        subset = first_order[(first_order["from_state"] == from_state) & (first_order["to_state"] == to_state)]
        mapping = subset.set_index("security_id")["transition_probability"]
        return data["security_id"].map(mapping).fillna(0)

    data["as_of_date"] = as_of
    data["risk_reframing_score"] = data[["risk_reframing_score_30d", "risk_reframing_score_90d"]].max(axis=1)
    data["positive_reframing_score"] = data[["positive_reframing_score_30d", "positive_reframing_score_90d"]].max(axis=1)
    data["markov_neutral_to_negative_prob"] = prob("neutral", "negative_deteriorating")
    data["markov_negative_to_distress_prob"] = prob("negative_deteriorating", "distress")
    data["markov_positive_to_dividend_risk_prob"] = prob("positive_stable", "dividend_risk")
    data["markov_credit_stress_to_distress_prob"] = prob("credit_stress", "distress")
    data["reframing_review_required_flag"] = (
        (data["risk_reframing_score"] > 80)
        | (data["dividend_risk_similarity_score"] > 85)
        | (data["credit_stress_similarity_score"] > 85)
        | (data["governance_risk_similarity_score"] > 85)
        | (data["regulatory_risk_similarity_score"] > 85)
    )
    data["reframing_exclusion_flag"] = (data["distress_similarity_score"] > 90) | (data["markov_negative_to_distress_prob"] > 0.35)
    data["narrative_reframing_score"] = (
        100
        - 0.35 * data["risk_reframing_score"]
        - 0.25 * data["narrative_instability_score"]
        + 0.25 * data["positive_reframing_score"]
        - 0.15 * data["distress_similarity_score"]
    ).clip(0, 100)
    columns = [
        "security_id",
        "ticker",
        "as_of_date",
        "new_risk_concept_count_30d",
        "recurring_risk_concept_count_90d",
        "concept_reoccurrence_intensity",
        "concept_acceleration_score",
        "semantic_drift_30d",
        "semantic_drift_90d",
        "narrative_instability_score",
        "risk_reframing_score",
        "positive_reframing_score",
        "distress_similarity_score",
        "dividend_risk_similarity_score",
        "credit_stress_similarity_score",
        "governance_risk_similarity_score",
        "regulatory_risk_similarity_score",
        "markov_neutral_to_negative_prob",
        "markov_negative_to_distress_prob",
        "markov_positive_to_dividend_risk_prob",
        "markov_credit_stress_to_distress_prob",
        "reframing_review_required_flag",
        "reframing_exclusion_flag",
        "narrative_reframing_score",
    ]
    return data[columns]
