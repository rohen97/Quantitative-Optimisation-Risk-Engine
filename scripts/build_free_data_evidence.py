from __future__ import annotations

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DuckDBRepository
from src.reporting.free_data_evidence import build_free_data_evidence
from src.utils.config import ROOT


def main() -> int:
    config = load_data_config()
    repository = DuckDBRepository(config.duckdb_path, read_only=True)
    result = build_free_data_evidence(
        repository,
        ROOT / "reports" / "outputs" / "validation",
        ROOT / "reports" / "outputs" / "validation",
    )
    print(result.summary.to_string(index=False))
    print(f"Manifest: {result.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
