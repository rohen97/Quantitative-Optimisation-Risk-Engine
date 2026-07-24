from __future__ import annotations

from collections.abc import Callable

import pandas as pd


def run_parameter_sensitivity(
    parameters: dict[str, float],
    changes: list[float],
    evaluator: Callable[[dict[str, float]], dict[str, float]],
) -> pd.DataFrame:
    baseline = evaluator(parameters)
    rows = []
    for name, value in parameters.items():
        for change in changes:
            varied = dict(parameters)
            varied[name] = value * (1.0 + change)
            result = evaluator(varied)
            rows.append({"parameter": name, "relative_change": change, "baseline_value": value, "varied_value": varied[name], **{f"{key}_change": result.get(key, 0.0) - baseline.get(key, 0.0) for key in result}})
    return pd.DataFrame(rows)
