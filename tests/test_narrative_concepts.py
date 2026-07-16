from src.data_ingestion.universe import build_universe
from src.narrative.concept_extraction import extract_financial_concepts
from src.narrative.mock_narrative_data import generate_mock_narrative_documents
from src.narrative.occurrence_tracker import track_concept_occurrences


def test_mock_narrative_documents_and_concepts():
    universe = build_universe()
    documents = generate_mock_narrative_documents(universe)
    concepts = extract_financial_concepts(documents)
    assert not documents.empty
    assert not concepts.empty
    assert "India" not in set(universe["region"])
    assert {"concept_text", "concept_category", "concept_polarity", "concept_severity"}.issubset(concepts.columns)


def test_occurrence_tracking_flags_risk_and_reoccurrence():
    concepts = extract_financial_concepts(generate_mock_narrative_documents(build_universe()))
    occurrences = track_concept_occurrences(concepts)
    assert "first_appearance_date" in occurrences.columns
    assert "recurring_risk_flag" in occurrences.columns
    assert occurrences["concept_reoccurrence_count"].max() >= 1
