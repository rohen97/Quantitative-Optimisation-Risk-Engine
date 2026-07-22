from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_ingestion.fundamental_ingestion import load_fundamentals
from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.universe import build_universe
from src.drl.baseline_policy import choose_baseline_portfolio
from src.drl.drl_pipeline import run_drl_pipeline
from src.pipeline import attach_drl_challenger_status
from src.portfolio.portfolio_loader import load_current_portfolio
from src.reporting.report_writer import write_csv
from src.utils.config import ensure_output_dir, load_yaml


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


DRL_INPUT_FILES = {
    "portfolio_optimisation_summary": "portfolio_optimisation_summary.csv",
    "optimised_portfolio_cvar_constrained": "optimised_portfolio_cvar_constrained.csv",
    "optimised_portfolio_regime_aware": "optimised_portfolio_regime_aware.csv",
    "optimised_portfolio_score_weighted": "optimised_portfolio_score_weighted.csv",
    "stock_scorecard": "stock_scorecard.csv",
    "return_distribution_forecasts": "return_distribution_forecasts.csv",
    "ml_forecasts_12m": "ml_forecasts_12m.csv",
    "regime_dashboard_summary": "regime_dashboard_summary.csv",
    "regime_suitability_scores": "regime_suitability_scores.csv",
    "alt_features_monthly": "alt_features_monthly.csv",
    "narrative_reframing_features": "narrative_reframing_features.csv",
    "risk_contribution_report": "risk_contribution_report.csv",
    "stress_test_report": "stress_test_report.csv",
    "stress_test_contribution_report": "stress_test_contribution_report.csv",
}


PIPELINE_STAGES = [
    "load settings",
    "load optimiser baseline portfolio",
    "load current portfolio",
    "load price history",
    "load scorecard",
    "load distributional forecasts",
    "load regime outputs",
    "load sentiment and narrative outputs",
    "load risk contributions",
    "load stress tests",
    "construct point-in-time DRL states",
    "validate state dimensions",
    "validate eligibility masks",
    "build market environment",
    "run environment smoke test",
    "train PPO or mock fallback",
    "train specialist policies where enabled",
    "run walk-forward validation",
    "run multi-seed backtests",
    "produce raw DRL weights",
    "apply regime gating",
    "apply Wolf Chaos risk throttle",
    "project weights to hard constraints",
    "compare against benchmarks",
    "run ablation tests",
    "generate explanations",
    "generate trade list",
    "run acceptance decision",
    "save all outputs",
    "update full-pipeline final recommendations with DRL challenger status",
]


def _read_output(output_dir: Path, filename: str) -> pd.DataFrame:
    path = output_dir / filename
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _load_upstream_frames(output_dir: Path) -> dict[str, pd.DataFrame]:
    frames = {name: _read_output(output_dir, filename) for name, filename in DRL_INPUT_FILES.items()}
    missing = [filename for name, filename in DRL_INPUT_FILES.items() if frames[name].empty]
    if missing:
        logging.info("Optional upstream DRL inputs missing or empty: %s", ", ".join(missing))
    return frames


def _validate_drl_outputs(outputs: dict[str, pd.DataFrame | str]) -> None:
    state_schema = outputs["drl_state_schema"]
    target_weights = outputs["drl_target_weights"]
    if not isinstance(state_schema, pd.DataFrame) or state_schema.empty:
        raise ValueError("DRL state schema validation failed: no state dimensions were produced.")
    if not isinstance(target_weights, pd.DataFrame) or target_weights.empty:
        raise ValueError("DRL target weight validation failed: no target weights were produced.")
    if "eligible_for_drl" not in target_weights:
        raise ValueError("DRL eligibility mask validation failed: eligible_for_drl column is missing.")
    if target_weights["eligible_for_drl"].isna().any():
        raise ValueError("DRL eligibility mask validation failed: mask contains missing values.")


def _update_final_recommendations(output_dir: Path, outputs: dict[str, pd.DataFrame | str]) -> None:
    path = output_dir / "final_recommendations.csv"
    if not path.exists():
        logging.info("final_recommendations.csv not found; skipping DRL challenger overlay update.")
        return
    final_recommendations = pd.read_csv(path)
    updated = attach_drl_challenger_status(final_recommendations, outputs)
    write_csv(updated, output_dir, "final_recommendations.csv")


def main() -> dict[str, pd.DataFrame | str]:
    for index, stage in enumerate(PIPELINE_STAGES, start=1):
        logging.info("DRL stage %02d: %s", index, stage)

    base_config = load_yaml("configs/base.yaml")
    drl_config = load_yaml("configs/drl.yaml").get("drl", load_yaml("configs/drl.yaml"))
    optimisation_config = load_yaml("configs/optimisation.yaml")
    output_dir = ensure_output_dir(base_config)
    frames = _load_upstream_frames(output_dir)

    baseline = choose_baseline_portfolio(frames, output_dir)
    if baseline.empty:
        raise ValueError("DRL pipeline requires an optimiser baseline portfolio before training or backtesting.")
    frames["recommended_optimised_portfolio"] = baseline
    logging.info("Loaded optimiser baseline portfolio with %s rows.", len(baseline))

    current_path = base_config.get("current_portfolio_path", "data/external/current_portfolio_template.csv")
    current_portfolio = load_current_portfolio(current_path)
    logging.info("Loaded current portfolio with %s rows.", len(current_portfolio))

    universe = build_universe(n=int(base_config.get("mock_data", {}).get("securities", 24)))
    price_history = load_prices(universe)
    fundamentals = load_fundamentals(universe)
    logging.info("Loaded price history with %s rows and fundamentals with %s rows.", len(price_history), len(fundamentals))

    outputs = run_drl_pipeline(
        output_dir,
        input_frames=frames,
        drl_config=drl_config,
        optimisation_config=optimisation_config,
        write_outputs=True,
    )
    _validate_drl_outputs(outputs)
    _update_final_recommendations(output_dir, outputs)
    decision = outputs["drl_acceptance_decision"]
    if isinstance(decision, pd.DataFrame) and not decision.empty:
        row = decision.iloc[0]
        logging.info(
            "DRL decision: accepted=%s, selected_weights_source=%s, drl_blend=%s, baseline_blend=%s.",
            row.get("accepted"),
            row.get("selected_weights_source"),
            row.get("blend_weight_drl"),
            row.get("blend_weight_baseline"),
        )
    logging.info("Constrained regime-gated explainable DRL pipeline completed with %s output artifacts.", len(outputs))
    return outputs


if __name__ == "__main__":
    main()
