from __future__ import annotations

import pandas as pd

from src.narrative.concept_extraction import extract_financial_concepts
from src.narrative.frame_builder import build_narrative_frames
from src.narrative.markov_transitions import build_markov_transitions
from src.narrative.mock_narrative_data import generate_mock_narrative_documents
from src.narrative.narrative_features import build_narrative_reframing_features
from src.narrative.occurrence_tracker import track_concept_occurrences
from src.narrative.semantic_distance import calculate_semantic_distances
from src.narrative.temporal_reframing import analyse_temporal_reframing, assign_narrative_state


def run_narrative_pipeline(
    universe: pd.DataFrame,
    narrative_config: dict | None = None,
    documents: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    """Run the full mock financial narrative reframing pipeline."""
    config = (narrative_config or {}).get("narrative", narrative_config or {})
    documents = documents.copy() if documents is not None else generate_mock_narrative_documents(universe)
    concepts = extract_financial_concepts(documents, min_confidence=config.get("min_concept_confidence", 60))
    occurrences = track_concept_occurrences(concepts)
    frames = build_narrative_frames(concepts, min_confidence=config.get("min_frame_confidence", 60))
    distances = calculate_semantic_distances(frames, provider=config.get("embedding_provider", "mock"))
    if not distances.empty:
        distances["narrative_state"] = distances.apply(assign_narrative_state, axis=1)
    temporal = analyse_temporal_reframing(distances)
    markov = build_markov_transitions(distances)
    features = build_narrative_reframing_features(occurrences, temporal, markov)
    return {
        "narrative_documents": documents,
        "narrative_concepts": concepts,
        "narrative_occurrences": occurrences,
        "narrative_frames": frames,
        "narrative_semantic_distances": distances,
        "narrative_temporal_features": temporal,
        "narrative_markov_transitions": markov,
        "narrative_reframing_features": features,
    }
