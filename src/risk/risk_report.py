from __future__ import annotations

import pandas as pd


def format_risk_report(report: pd.DataFrame) -> pd.DataFrame:
    return report.copy()
