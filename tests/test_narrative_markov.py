from src.data_ingestion.universe import build_universe
from src.narrative.pipeline import run_narrative_pipeline


def test_markov_transitions_are_produced():
    outputs = run_narrative_pipeline(build_universe())
    transitions = outputs["narrative_markov_transitions"]
    assert not transitions.empty
    assert {1, 2}.intersection(set(transitions["transition_order"]))
    assert transitions["transition_probability"].between(0, 1).all()
