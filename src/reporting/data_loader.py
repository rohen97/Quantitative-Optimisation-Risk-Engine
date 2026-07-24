from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import replace
import hashlib
import logging
from pathlib import Path

import pandas as pd

from src.data.config import load_data_config
from src.data.repository.repository_router import repository_for_mode
from src.reporting.column_resolver import canonicalise_dataframe
from src.reporting.models import ICDataBundle, ReportSource


LOGGER = logging.getLogger(__name__)

CSV_OUTPUTS = {
    "current_portfolio": "current_portfolio_enriched.csv",
    "current_diagnostics": "current_portfolio_diagnostics.csv",
    "final_portfolio_weights": "final_portfolio_weights.csv",
    "final_portfolio": "final_portfolio_weights.csv",
    "portfolio_optimisation_summary": "portfolio_optimisation_summary.csv",
    "portfolio_constraint_report": "portfolio_constraint_report.csv",
    "sector_exposure": "sector_exposure.csv",
    "country_exposure": "country_exposure.csv",
    "region_exposure": "region_exposure.csv",
    "currency_exposure": "currency_exposure.csv",
    "final_recommendations": "final_recommendations.csv",
    "branch_comparison": "branch_comparison_report.csv",
    "llm_benchmark_results": "llm_benchmark_results.csv",
    "portfolio_trade_list": "portfolio_trade_list.csv",
    "recommendations_portfolio_aware": "recommendations_portfolio_aware.csv",
    "recommendations_clean_sheet": "recommendations_clean_sheet.csv",
    "optimised_portfolio_score_weighted": "optimised_portfolio_score_weighted.csv",
    "optimised_portfolio_risk_parity": "optimised_portfolio_risk_parity.csv",
    "optimised_portfolio_mean_variance": "optimised_portfolio_mean_variance.csv",
    "optimised_portfolio_cvar_constrained": "optimised_portfolio_cvar_constrained.csv",
    "optimised_portfolio_dividend_income": "optimised_portfolio_dividend_income.csv",
    "optimised_portfolio_regime_aware": "optimised_portfolio_regime_aware.csv",
    "ml_forecasts_3m": "ml_forecasts_3m.csv",
    "ml_forecasts_6m": "ml_forecasts_6m.csv",
    "ml_forecasts_9m": "ml_forecasts_9m.csv",
    "ml_forecasts_12m": "ml_forecasts_12m.csv",
    "dividend_cut_probability": "dividend_cut_probability.csv",
    "drawdown_probability": "drawdown_probability.csv",
    "regime_suitability": "regime_suitability_scores.csv",
    "regime_transition_matrix": "regime_transition_matrix.csv",
    "regime_informational_drivers": "regime_informational_drivers.csv",
    "drl_trade_list": "drl_trade_list.csv",
    "drl_acceptance": "drl_acceptance_decision.csv",
    "drl_target_weights": "drl_target_weights.csv",
    "drl_constraints": "drl_constraint_adjustments.csv",
    "drl_reward_decomposition": "drl_reward_decomposition.csv",
    "drl_regime_agent_weights": "drl_regime_agent_weights.csv",
    "drl_explanations": "drl_explanations.csv",
    "drl_feature_attributions": "drl_feature_attributions.csv",
    "drl_asset_time_attributions": "drl_asset_time_attributions.csv",
    "drl_benchmark_comparison": "drl_benchmark_comparison.csv",
    "drl_seed_results": "drl_seed_results.csv",
    "drl_ablation_results": "drl_ablation_results.csv",
    "risk_report": "portfolio_risk_report.csv",
    "risk_contribution": "risk_contribution_report.csv",
    "stress_report": "stress_test_report.csv",
    "stress_contribution": "stress_test_contribution_report.csv",
    "regime_summary": "regime_dashboard_summary.csv",
    "factor_regime_probabilities": "factor_regime_probabilities.csv",
    "chaos_regime_probabilities": "chaos_regime_probabilities.csv",
    "hedges": "hedge_recommendations.csv",
    "defensive_substitutions": "defensive_substitution_recommendations.csv",
    "features": "features_monthly.csv",
    "scorecard": "stock_scorecard.csv",
    "recommendations_3m": "recommendations_3m.csv",
    "recommendations_6m": "recommendations_6m.csv",
    "recommendations_9m": "recommendations_9m.csv",
    "recommendations_12m": "recommendations_12m.csv",
    "distribution_forecasts": "return_distribution_forecasts.csv",
    "data_backend_comparison": "data_backend_comparison.csv",
    "data_validation_report": "data_validation_report.csv",
    "model_run_lineage": "model_run_lineage.csv",
}

MD_OUTPUTS = {
    "risk_stress_hedge_summary": "risk_stress_hedge_summary.md",
    "model_validation_report": "model_validation_report.md",
    "drl_model_card": "drl_model_card.md",
    "drl_validation_report": "drl_validation_report.md",
    "data_backend_comparison_summary": "data_backend_comparison_summary.md",
}


def calculate_file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_read_csv(path: Path, source_name: str) -> tuple[pd.DataFrame, ReportSource]:
    if not path.exists():
        return (
            pd.DataFrame(),
            ReportSource(source_name, path, False, 0, None, None, "Source file is unavailable."),
        )
    try:
        data = pd.read_csv(path)
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return (
            canonicalise_dataframe(data),
            ReportSource(source_name, path, True, len(data), modified_at, calculate_file_hash(path)),
        )
    except Exception as error:
        LOGGER.exception("Failed to load reporting source %s", path)
        return (
            pd.DataFrame(),
            ReportSource(source_name, path, False, 0, None, None, str(error)),
        )


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _model_run_id(frames: dict[str, pd.DataFrame]) -> str:
    lineage = frames.get("model_run_lineage", pd.DataFrame())
    if not lineage.empty and "model_run_id" in lineage:
        return str(lineage.iloc[-1]["model_run_id"])
    return pd.Timestamp.utcnow().strftime("ic-%Y%m%d%H%M%S")


def _as_of_date(sources: list[ReportSource]) -> pd.Timestamp:
    available_dates = [source.modified_at for source in sources if source.modified_at is not None]
    if not available_dates:
        return pd.Timestamp.utcnow()
    return pd.Timestamp(max(available_dates))


def _validate_critical_inputs(frames: dict[str, pd.DataFrame]) -> None:
    has_current = not frames.get("current_portfolio", pd.DataFrame()).empty
    has_target = any(
        not frames.get(name, pd.DataFrame()).empty
        for name in ("final_portfolio_weights", "final_recommendations", "portfolio_trade_list", "drl_target_weights")
    )
    if not has_current and not has_target:
        raise FileNotFoundError(
            "IC reporting requires a current portfolio or at least one target/recommended portfolio output. "
            "Run the model pipeline first or provide reports/outputs/current_portfolio_enriched.csv, "
            "reports/outputs/final_recommendations.csv, or reports/outputs/portfolio_trade_list.csv."
        )


def load_ic_data(
    output_root: str | Path = "reports/outputs",
    *,
    model_run_id: str | None = None,
    as_of_date: str | pd.Timestamp | None = None,
    backend: str = "legacy_csv",
) -> ICDataBundle:
    root = Path(output_root)
    frames: dict[str, pd.DataFrame] = {}
    sources: list[ReportSource] = []
    for name, filename in CSV_OUTPUTS.items():
        frame, source = safe_read_csv(root / filename, name)
        frames[name] = frame
        sources.append(source)
    _validate_critical_inputs(frames)
    markdown = {name: _read_text(root / filename) for name, filename in MD_OUTPUTS.items()}
    return ICDataBundle(
        frames=frames,
        markdown=markdown,
        source_root=root,
        sources=sources,
        model_run_id=model_run_id or _model_run_id(frames),
        as_of_date=pd.Timestamp(as_of_date) if as_of_date is not None else _as_of_date(sources),
        metadata={"backend": backend},
    )


def load_ic_data_from_config(
    output_root: str | Path = "reports/outputs",
    *,
    backend_override: str | None = None,
    model_run_id: str | None = None,
    as_of_date: str | pd.Timestamp | None = None,
) -> ICDataBundle:
    config = load_data_config()
    if backend_override is not None:
        if backend_override not in {"legacy_csv", "duckdb", "shadow"}:
            raise ValueError(f"Unsupported reporting backend: {backend_override}")
        config = replace(config, backend=backend_override)
    repository_for_mode(config, csv_root=output_root)
    return load_ic_data(
        output_root,
        model_run_id=model_run_id,
        as_of_date=as_of_date,
        backend=config.backend,
    )
