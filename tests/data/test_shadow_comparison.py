import pandas as pd

from src.data.comparison.frame_compare import compare_frames
from src.data.comparison.backend_shadow_compare import compare_legacy_and_duckdb_frames
from src.data.config import DataLayerConfig


def test_shadow_comparison_reports_matching_and_differences():
    left = pd.DataFrame({"ticker": ["AAA"], "value": [1.0]})
    right = pd.DataFrame({"ticker": ["AAA"], "value": [1.0000001]})
    assert compare_frames(left, right, numeric_tolerance=1e-5).matched
    report = compare_legacy_and_duckdb_frames({"x": left}, {"x": right}, DataLayerConfig(backend="shadow", relative_tolerance=1e-5))
    assert report.loc[0, "matched"]
