from __future__ import annotations

import pandas as pd

from src.data.comparison.frame_compare import compare_frames
from src.data.config import DataLayerConfig


def compare_legacy_and_duckdb_frames(
    legacy_frames: dict[str, pd.DataFrame],
    duckdb_frames: dict[str, pd.DataFrame],
    config: DataLayerConfig,
) -> pd.DataFrame:
    rows = []
    for name in sorted(set(legacy_frames) | set(duckdb_frames)):
        result = compare_frames(
            legacy_frames.get(name, pd.DataFrame()),
            duckdb_frames.get(name, pd.DataFrame()),
            numeric_tolerance=config.numeric_tolerance,
            row_count_tolerance=config.row_count_tolerance,
        )
        rows.append({"frame_name": name, "matched": result.matched, **result.__dict__})
    return pd.DataFrame(rows)
