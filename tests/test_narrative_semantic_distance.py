from src.data_ingestion.universe import build_universe
from src.narrative.concept_extraction import extract_financial_concepts
from src.narrative.embedding_engine import embed_texts
from src.narrative.frame_builder import build_narrative_frames
from src.narrative.mock_narrative_data import generate_mock_narrative_documents
from src.narrative.semantic_distance import calculate_semantic_distances
from src.narrative.temporal_reframing import analyse_temporal_reframing


def test_mock_embeddings_and_semantic_distances():
    vectors = embed_texts(["strong cash flow", "credit downgrade"])
    assert len(vectors) == 2
    assert len(vectors[0]) == 16
    frames = build_narrative_frames(extract_financial_concepts(generate_mock_narrative_documents(build_universe())))
    distances = calculate_semantic_distances(frames)
    assert not distances.empty
    assert distances["semantic_drift_score"].between(0, 100).all()


def test_temporal_reframing_assigns_states():
    frames = build_narrative_frames(extract_financial_concepts(generate_mock_narrative_documents(build_universe())))
    distances = calculate_semantic_distances(frames)
    temporal = analyse_temporal_reframing(distances)
    assert not temporal.empty
    assert "latest_narrative_state" in temporal.columns
