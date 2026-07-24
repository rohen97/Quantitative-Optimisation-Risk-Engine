from __future__ import annotations

import pandas as pd


def leave_one_group_out(data: pd.DataFrame, group_column: str, value_column: str) -> pd.DataFrame:
    if data.empty or group_column not in data or value_column not in data:
        return pd.DataFrame()
    full = float(pd.to_numeric(data[value_column], errors="coerce").mean())
    rows = []
    for group in data[group_column].dropna().unique():
        remaining = pd.to_numeric(data.loc[data[group_column] != group, value_column], errors="coerce").dropna()
        result = float(remaining.mean()) if not remaining.empty else float("nan")
        rows.append({"excluded_group": group, "full_value": full, "leave_one_out_value": result, "change": result - full})
    return pd.DataFrame(rows)
