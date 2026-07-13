from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class AllocationState:
    weights: pd.Series
    features: pd.DataFrame
    covariance_matrix: pd.DataFrame
