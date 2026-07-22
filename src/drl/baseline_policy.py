from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.optimisation.constraints import build_eligibility_mask


BASELINE_FILES = [
    "optimised_portfolio_cvar_constrained.csv",
    "optimised_portfolio_regime_aware.csv",
    "optimised_portfolio_score_weighted.csv",
]


def selected_baseline_method(summary: pd.DataFrame) -> str | None:
    """Extract the selected classical optimiser method from the summary."""
    if summary is None or summary.empty or "selected_recommended_portfolio" not in summary:
        return None
    selected = summary[summary["selected_recommended_portfolio"].astype(bool)]
    if selected.empty:
        return None
    return str(selected.iloc[0]["portfolio_method"])


def choose_baseline_portfolio(
    outputs: dict[str, pd.DataFrame] | None = None,
    output_dir: str | Path = "reports/outputs",
) -> pd.DataFrame:
    """Choose the default baseline using the requested priority order."""
    frames = outputs or {}
    summary = frames.get("portfolio_optimisation_summary", pd.DataFrame())
    selected = selected_baseline_method(summary)
    if selected:
        for frame in frames.values():
            if isinstance(frame, pd.DataFrame) and "portfolio_method" in frame and not frame.empty:
                if str(frame["portfolio_method"].iloc[0]) == selected:
                    return frame.copy()
    for key in ["recommended_optimised_portfolio", "optimised_portfolio_cvar_constrained", "optimised_portfolio_regime_aware"]:
        frame = frames.get(key, pd.DataFrame())
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            return frame.copy()
    output_path = Path(output_dir)
    for filename in BASELINE_FILES:
        path = output_path / filename
        if path.exists():
            return pd.read_csv(path)
    scorecard = frames.get("stock_scorecard", pd.DataFrame())
    if scorecard.empty and (output_path / "stock_scorecard.csv").exists():
        scorecard = pd.read_csv(output_path / "stock_scorecard.csv")
    if not scorecard.empty:
        data = scorecard.copy()
        score = data.get("final_recommendation_score", pd.Series(1.0, index=data.index)).fillna(1.0).clip(lower=0)
        weights = score / score.sum() if score.sum() > 0 else pd.Series(1 / len(data), index=data.index)
        data["target_weight"] = weights
        data["portfolio_method"] = "score_weighted_fallback"
        data["eligible_for_optimisation"] = build_eligibility_mask(data, {})
        return data
    return pd.DataFrame()


def baseline_weight_vector(portfolio: pd.DataFrame) -> np.ndarray:
    """Return target weights normalised to one for listed assets."""
    if portfolio.empty:
        return np.array([], dtype=float)
    weights = pd.to_numeric(portfolio.get("target_weight", 0.0), errors="coerce").fillna(0.0).clip(lower=0)
    total = float(weights.sum())
    return (weights / total).to_numpy(dtype=float) if total > 0 else weights.to_numpy(dtype=float)
