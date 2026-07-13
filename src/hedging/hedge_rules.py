from __future__ import annotations

import pandas as pd


def hedge_need_from_stress(stress_report: pd.DataFrame) -> str:
    return "High" if stress_report["portfolio_loss_pct"].min() < -0.18 else "Moderate"
