from pathlib import Path
import subprocess
import sys

from src.pipeline import run_full_pipeline


def test_run_narrative_engine_script_creates_outputs():
    result = subprocess.run([sys.executable, "scripts/run_narrative_engine.py"], check=True, capture_output=True, text=True)
    assert result.returncode == 0
    assert Path("reports/outputs/narrative_reframing_features.csv").exists()


def test_full_pipeline_includes_narrative_outputs(tmp_path):
    outputs = run_full_pipeline(tmp_path)
    assert "narrative_reframing_features" in outputs
    assert "narrative_reframing_score" in outputs["scorecard"].columns
    for filename in [
        "narrative_concepts.csv",
        "narrative_frames.csv",
        "narrative_semantic_distances.csv",
        "narrative_markov_transitions.csv",
        "narrative_reframing_features.csv",
    ]:
        assert (Path(tmp_path) / filename).exists()
