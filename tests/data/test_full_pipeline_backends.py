from src.data.config import load_data_config
from src.pipeline import run_full_pipeline


def test_full_pipeline_uses_configured_backend(tmp_path):
    config = load_data_config()
    assert config.mode == "duckdb"
    outputs = run_full_pipeline(tmp_path)
    assert "final_recommendations" in outputs
    assert outputs["final_recommendations"].shape[0] > 0
