import pandas as pd

from src.data.lineage import new_model_run_lineage
from src.data.lineage import calculate_json_hash, get_git_metadata
from src.data.repository.duckdb_repository import DuckDBRepository


def test_model_run_lineage_can_be_persisted(tmp_path):
    lineage = new_model_run_lineage("legacy_csv", code_version="test", config_hash="abc", input_snapshot_id="snap")
    repo = DuckDBRepository(tmp_path / "lineage.duckdb")
    repo.execute_migrations("sql/migrations")
    repo.write_table("model_runs", pd.DataFrame([lineage.__dict__]), ("model_run_id",))
    loaded = repo.read_table("model_runs")
    repo.close()
    assert loaded.loc[0, "backend"] == "legacy_csv"
    assert loaded.loc[0, "input_snapshot_hash"] == "snap"


def test_lineage_hash_is_deterministic(tmp_path):
    assert calculate_json_hash({"b": 2, "a": 1}) == calculate_json_hash({"a": 1, "b": 2})
    commit, dirty = get_git_metadata(tmp_path)
    assert commit is None
    assert dirty is False
