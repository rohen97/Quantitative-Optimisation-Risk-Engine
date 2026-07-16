from pathlib import Path

import pandas as pd

from src.narrative.mock_narrative_data import load_narrative_documents
from src.narrative.pipeline import run_narrative_pipeline


FIXTURE_PATH = Path("tests/fixtures/narrative_known_timeline.csv")
EXPECTED_TRANSITIONS_PATH = Path("tests/fixtures/narrative_expected_transitions.csv")


def fixture_universe(documents: pd.DataFrame) -> pd.DataFrame:
    return (
        documents[["security_id", "ticker", "company_name", "country"]]
        .drop_duplicates()
        .assign(
            region="DACH",
            currency="EUR",
            sector="Industrials",
            market_cap_usd=1_000_000_000,
            avg_daily_traded_value_usd=10_000_000,
        )
    )


def test_known_fixture_narrative_state_path():
    documents = load_narrative_documents(FIXTURE_PATH)
    outputs = run_narrative_pipeline(fixture_universe(documents), documents=documents)
    states = outputs["narrative_semantic_distances"].sort_values("publication_timestamp")["narrative_state"].tolist()
    assert states[0] == "positive_stable"
    assert "governance_risk" in states
    assert "distress" in states
    assert states[-1] == "credit_stress"


def test_known_fixture_expected_markov_transitions():
    documents = load_narrative_documents(FIXTURE_PATH)
    outputs = run_narrative_pipeline(fixture_universe(documents), documents=documents)
    transitions = outputs["narrative_markov_transitions"]
    expected = pd.read_csv(EXPECTED_TRANSITIONS_PATH).fillna("")
    for row in expected.itertuples(index=False):
        match = transitions[
            (transitions["transition_order"] == row.transition_order)
            & (transitions["from_state"] == row.from_state)
            & (transitions["intermediate_state"].fillna("") == row.intermediate_state)
            & (transitions["to_state"] == row.to_state)
            & (transitions["transition_probability"] >= row.min_probability)
        ]
        assert not match.empty


def test_known_fixture_reframing_features_flag_distress():
    documents = load_narrative_documents(FIXTURE_PATH)
    outputs = run_narrative_pipeline(fixture_universe(documents), documents=documents)
    features = outputs["narrative_reframing_features"]
    assert features.loc[0, "reframing_review_required_flag"]
    assert features.loc[0, "reframing_exclusion_flag"]
    assert features.loc[0, "distress_similarity_score"] >= 90
    assert features.loc[0, "credit_stress_similarity_score"] >= 90
