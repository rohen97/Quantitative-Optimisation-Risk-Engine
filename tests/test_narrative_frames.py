from src.data_ingestion.universe import build_universe
from src.narrative.concept_extraction import extract_financial_concepts
from src.narrative.frame_builder import build_narrative_frames
from src.narrative.mock_narrative_data import generate_mock_narrative_documents


def test_narrative_frames_are_created_from_co_occurring_concepts():
    concepts = extract_financial_concepts(generate_mock_narrative_documents(build_universe()))
    frames = build_narrative_frames(concepts)
    assert not frames.empty
    assert {"frame_id", "frame_label", "concepts_in_frame", "frame_severity"}.issubset(frames.columns)
