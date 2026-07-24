import json

from src.validation.validation_pipeline import OUTPUT_FILES, run_validation_pipeline


def test_validation_pipeline_preserves_runs_and_updates_latest(tmp_path):
    first = run_validation_pipeline(output_root=tmp_path, execution_mode="smoke", run_sensitivity=False, run_ablation=False)
    second = run_validation_pipeline(output_root=tmp_path, execution_mode="full")
    assert first.output_directory.exists()
    assert second.output_directory.exists()
    assert first.output_directory != second.output_directory
    for filename in OUTPUT_FILES:
        assert (second.output_directory / filename).exists()
        assert (tmp_path / "latest" / filename).exists()
    manifest = json.loads((second.output_directory / "validation_manifest.json").read_text(encoding="utf-8"))
    assert manifest["validation_run_id"] == second.validation_run_id
    assert manifest["approval_status"] in {"APPROVED", "CONDITIONALLY_APPROVED", "REJECTED", "INSUFFICIENT_DATA"}
