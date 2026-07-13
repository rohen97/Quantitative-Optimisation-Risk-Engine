from __future__ import annotations

import pandas as pd


def evaluate_risk_limits(report: pd.DataFrame, max_var: float = 0.08, max_cvar: float = 0.12) -> pd.DataFrame:
    data = report.copy()
    data["var_limit_pass"] = data["var_5"].abs() <= max_var
    data["cvar_limit_pass"] = data["cvar_5"].abs() <= max_cvar
    return data
