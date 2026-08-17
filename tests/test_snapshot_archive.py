from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.repository.duckdb_repository import DuckDBRepository
from src.validation.snapshot_archive import archive_walk_forward_snapshots


def test_archive_walk_forward_snapshots_is_deterministic(tmp_path: Path) -> None:
    artifacts = tmp_path / "walk_forward"
    artifacts.mkdir()
    weights = pd.DataFrame(
        {
            "security_id": ["SEC-1", "SEC-2", "SEC-1"],
            "as_of_date": ["2024-01-31"] * 3,
            "strategy": ["equal_weight_eligible", "equal_weight_eligible", "wolf_cvar"],
            "weight": [0.5, 0.5, 1.0],
            "revenue_growth": [0.1, 0.2, 0.1],
            "final_recommendation_score": [70.0, 80.0, 70.0],
            "recommendation": ["hold", "buy", "hold"],
        }
    )
    forecasts = pd.DataFrame(
        {
            "security_id": ["SEC-1", "SEC-2"],
            "as_of_date": ["2024-01-31"] * 2,
            "horizon": ["12m", "12m"],
            "expected_total_return": [0.1, 0.2],
            "model_version": ["test-v1", "test-v1"],
        }
    )
    weights.to_parquet(artifacts / "historical_portfolio_weights.parquet", index=False)
    forecasts.to_parquet(artifacts / "historical_forecasts.parquet", index=False)

    repository = DuckDBRepository(tmp_path / "archive.duckdb")
    repository.execute_migrations(Path("sql/migrations"))
    first = archive_walk_forward_snapshots(
        artifacts,
        repository=repository,
        project_root=Path.cwd(),
    )
    second = archive_walk_forward_snapshots(
        artifacts,
        repository=repository,
        project_root=Path.cwd(),
    )

    assert first == second
    assert first.manifests == 1
    assert first.feature_rows == 2
    assert first.forecast_rows == 2
    assert first.scorecard_rows == 2
    assert first.portfolio_rows == 3
    manifests = repository.read_table("decision_snapshot_manifests")
    assert len(manifests) == 1
    assert manifests.loc[0, "source"] == "retrospective_walk_forward_archive"
    assert manifests.loc[0, "model_version"].startswith("test-v1+src.")
