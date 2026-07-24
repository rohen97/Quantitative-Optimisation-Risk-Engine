from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FrameComparison:
    equal: bool
    row_count_left: int
    row_count_right: int
    missing_keys_left: int
    missing_keys_right: int
    differing_numeric_cells: int
    maximum_absolute_difference: float
    maximum_relative_difference: float

    @property
    def matched(self) -> bool:
        return self.equal

    @property
    def row_count_difference(self) -> int:
        return abs(self.row_count_left - self.row_count_right)

    @property
    def max_numeric_difference(self) -> float:
        return self.maximum_absolute_difference


FrameComparisonResult = FrameComparison


def _default_numeric_columns(left: pd.DataFrame, right: pd.DataFrame) -> list[str]:
    return [
        column
        for column in left.columns.intersection(right.columns)
        if pd.api.types.is_numeric_dtype(left[column]) and pd.api.types.is_numeric_dtype(right[column])
    ]


def compare_frames(
    left: pd.DataFrame,
    right: pd.DataFrame,
    key_columns: list[str] | None = None,
    numeric_columns: list[str] | None = None,
    absolute_tolerance: float = 1e-8,
    relative_tolerance: float = 1e-6,
    numeric_tolerance: float | None = None,
    row_count_tolerance: int = 0,
) -> FrameComparison:
    if numeric_tolerance is not None:
        absolute_tolerance = numeric_tolerance
    if left.empty and right.empty:
        return FrameComparison(True, 0, 0, 0, 0, 0, 0.0, 0.0)
    common_columns = list(left.columns.intersection(right.columns))
    if key_columns is None:
        key_columns = [common_columns[0]] if common_columns else []
    if numeric_columns is None:
        numeric_columns = _default_numeric_columns(left, right)
    if not key_columns:
        key_columns = ["__row_number"]
        left = left.copy().assign(__row_number=range(len(left)))
        right = right.copy().assign(__row_number=range(len(right)))

    left_aligned = left.sort_values(key_columns).reset_index(drop=True)
    right_aligned = right.sort_values(key_columns).reset_index(drop=True)
    left_keys = set(map(tuple, left_aligned[key_columns].astype(str).to_numpy()))
    right_keys = set(map(tuple, right_aligned[key_columns].astype(str).to_numpy()))
    common_keys = sorted(left_keys.intersection(right_keys))

    differing_numeric_cells = 0
    max_abs = 0.0
    max_rel = 0.0
    if common_keys and numeric_columns:
        left_common = left_aligned.assign(__key=list(map(tuple, left_aligned[key_columns].astype(str).to_numpy()))).set_index("__key").loc[common_keys]
        right_common = right_aligned.assign(__key=list(map(tuple, right_aligned[key_columns].astype(str).to_numpy()))).set_index("__key").loc[common_keys]
        left_values = left_common[numeric_columns].to_numpy(dtype=float)
        right_values = right_common[numeric_columns].to_numpy(dtype=float)
        absolute_difference = np.abs(left_values - right_values)
        denominator = np.maximum(np.abs(right_values), absolute_tolerance)
        relative_difference = absolute_difference / denominator
        close = np.isclose(left_values, right_values, atol=absolute_tolerance, rtol=relative_tolerance, equal_nan=True)
        differing_numeric_cells = int((~close).sum())
        max_abs = float(np.nanmax(absolute_difference) if absolute_difference.size else 0.0)
        max_rel = float(np.nanmax(relative_difference) if relative_difference.size else 0.0)

    equal = (
        len(left_keys - right_keys) <= row_count_tolerance
        and len(right_keys - left_keys) <= row_count_tolerance
        and differing_numeric_cells == 0
    )
    return FrameComparison(
        equal=equal,
        row_count_left=len(left),
        row_count_right=len(right),
        missing_keys_left=len(right_keys - left_keys),
        missing_keys_right=len(left_keys - right_keys),
        differing_numeric_cells=differing_numeric_cells,
        maximum_absolute_difference=max_abs,
        maximum_relative_difference=max_rel,
    )
