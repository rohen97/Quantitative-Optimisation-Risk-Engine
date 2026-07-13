from __future__ import annotations

import pandas as pd

from src.regime.regime_features import default_regime_inputs
from src.regime.regime_rules import build_regime_scores, classify_regime


def build_regime_features(universe: pd.DataFrame) -> pd.DataFrame:
    return build_regime_scores(universe, classify_regime(default_regime_inputs()))
