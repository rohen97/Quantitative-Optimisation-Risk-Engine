from src.reporting.narrative import FORBIDDEN_CAUSAL_WORDS, build_narrative


def test_narrative_avoids_causal_language():
    text = build_narrative({"dominant_regime": "stable", "wolf_chaos_index": 10})
    assert all(word not in text for word in FORBIDDEN_CAUSAL_WORDS)
