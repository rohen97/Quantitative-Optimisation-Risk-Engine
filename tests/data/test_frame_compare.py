import pandas as pd

from src.data.comparison.frame_compare import compare_frames


def test_frame_compare_aligns_keys_and_tolerances():
    left = pd.DataFrame({"ticker": ["B", "A"], "value": [2.0, 1.0]})
    right = pd.DataFrame({"ticker": ["A", "B"], "value": [1.0 + 1e-9, 2.0]})
    comparison = compare_frames(left, right, key_columns=["ticker"], numeric_columns=["value"])
    assert comparison.equal
    assert comparison.maximum_absolute_difference <= 1e-8
