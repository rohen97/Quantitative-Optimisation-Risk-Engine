from __future__ import annotations

import argparse
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.validation.snapshot_archive import archive_walk_forward_snapshots


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register immutable manifests and database snapshots for a walk-forward run."
    )
    parser.add_argument(
        "--artifact-directory",
        type=Path,
        default=Path("reports/outputs/walk_forward"),
    )
    parser.add_argument("--manifest-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = archive_walk_forward_snapshots(
        args.artifact_directory,
        write_detail_tables=not args.manifest_only,
    )
    print(
        "Archived "
        f"{result.manifests} manifests, {result.feature_rows} features, "
        f"{result.forecast_rows} forecasts, {result.scorecard_rows} scores, "
        f"and {result.portfolio_rows} portfolio weights."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
