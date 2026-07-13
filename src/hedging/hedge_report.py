from __future__ import annotations

import pandas as pd

from src.hedging.equity_hedges import build_equity_hedges
from src.hedging.institutional_hedges import build_institutional_hedges


def build_hedge_recommendations(portfolio: pd.DataFrame, include_institutional: bool = True) -> pd.DataFrame:
    frames = [build_equity_hedges(portfolio)]
    if include_institutional:
        frames.append(build_institutional_hedges())
    return pd.concat(frames, ignore_index=True)
