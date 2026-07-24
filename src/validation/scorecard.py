from __future__ import annotations

import pandas as pd


COMPONENT_WEIGHTS = {
    "data_integrity": 20.0,
    "point_in_time": 15.0,
    "forecast_performance": 15.0,
    "distribution_calibration": 10.0,
    "risk_backtesting": 15.0,
    "portfolio_net_of_costs": 10.0,
    "constraint_compliance": 10.0,
    "stability_sensitivity": 5.0,
}


def build_validation_scorecard(statuses: dict[str, str]) -> pd.DataFrame:
    rows = []
    for component, maximum in COMPONENT_WEIGHTS.items():
        status = statuses.get(component, "NOT_EVALUATED")
        score = maximum if status == "PASS" else maximum * 0.5 if status == "WARNING" else 0.0 if status == "FAIL" else float("nan")
        rows.append({"component": component, "maximum_score": maximum, "score": score, "status": status})
    return pd.DataFrame(rows)
