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

_LARGE_SOURCE_BYTES = 8 * 1024 * 1024
_IDENTIFIER_COLUMNS = (
    "security_id",
    "ticker",
    "issuer_id",
    "company_name",
    "country",
    "region",
    "sector",
    "currency",
)
_FORECAST_COLUMNS = (
    "horizon",
    "horizon_months",
    "expected_total_return",
    "expected_price_return",
    "expected_dividend_return",
    "expected_volatility",
    "expected_max_drawdown",
    "p5_return",
    "p50_return",
    "p95_return",
    "var_5",
    "var_1",
    "cvar_5",
    "cvar_1",
    "expected_shortfall_5",
    "expected_shortfall_1",
    "dividend_cut_probability",
    "large_drawdown_probability",
    "forecast_uncertainty_score",
    "regime_suitability_score",
    "distribution_name",
    "distribution_model_confidence",
    "distribution_family",
    "model_version",
)
_PORTFOLIO_COLUMNS = (
    *_IDENTIFIER_COLUMNS,
    "target_weight",
    "current_weight",
    "current_market_value_usd",
    "market_value_usd",
    "final_weight",
    "final_selected_weight",
    "final_recommendation",
    "recommendation",
    "final_recommendation_score",
    "portfolio_method",
    "eligible_for_optimisation",
    "fallback_eligibility_used",
    "expected_total_return_12m",
    "expected_dividend_return_12m",
    "expected_volatility_12m",
    "dividend_yield",
    "p5_return_12m",
    "p50_return_12m",
    "p95_return_12m",
    "var_5_12m",
    "cvar_5_12m",
    "expected_shortfall_5_12m",
    "dividend_cut_probability",
    "large_drawdown_probability_12m",
    "regime_suitability_score",
    "risk_management_flags",
    "sector_data_source",
    "liquidity_data_source",
    "market_cap_data_source",
    "fundamentals_data_source",
    "is_synthetic_data",
    "is_synthetic_fundamentals",
    "price_data_quality_score",
    "price_data_exclusion_flag",
    "optimisation_feasible",
    "optimisation_status",
)

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
    "llm_benchmark_results": "recommendations_llm_benchmark.csv",
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
    "regime_informational_drivers": "informational_driver_model.csv",
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


def _projected_columns(source_name: str, available: list[str]) -> list[str] | None:
    if source_name == "features":
        desired = _IDENTIFIER_COLUMNS
    elif source_name == "scorecard":
        desired = (
            *_IDENTIFIER_COLUMNS,
            "passes_hard_filters",
            "final_recommendation_score",
            "recommendation",
            "target_weight",
            "risk_management_flags",
            "expected_total_return_12m",
            "p5_return_12m",
            "p50_return_12m",
            "p95_return_12m",
            "dividend_cut_probability",
            "large_drawdown_probability_12m",
        )
    elif source_name in {"recommendations_portfolio_aware", "recommendations_clean_sheet"}:
        desired = (
            *_IDENTIFIER_COLUMNS,
            "final_recommendation",
            "recommendation",
            "target_weight",
            "final_recommendation_score",
        )
    elif source_name == "branch_comparison":
        desired = (
            "security_id",
            "ticker",
            "company_name",
            "portfolio_aware_recommendation",
            "clean_sheet_recommendation",
            "llm_recommendation",
            "branch_classification",
            "recommendation_agreement",
            "disagreement_flag",
        )
    elif source_name.startswith("optimised_portfolio_"):
        desired = _PORTFOLIO_COLUMNS
    elif source_name.startswith("ml_forecasts_") or source_name == "distribution_forecasts":
        desired = (*_IDENTIFIER_COLUMNS, *_FORECAST_COLUMNS)
    elif source_name.startswith("recommendations_"):
        desired = (*_IDENTIFIER_COLUMNS, *_FORECAST_COLUMNS)
    else:
        return None
    projected = [column for column in available if column in set(desired)]
    return projected or None


def _read_large_reporting_csv(path: Path, source_name: str) -> tuple[pd.DataFrame, int]:
    available = list(pd.read_csv(path, nrows=0).columns)
    if source_name == "stress_contribution":
        row_count = sum(len(chunk) for chunk in pd.read_csv(path, usecols=[available[0]], chunksize=50_000))
        return pd.DataFrame(columns=available), row_count
    usecols = _projected_columns(source_name, available)
    if usecols is None:
        data = pd.read_csv(path)
        return data, len(data)
    if not source_name.startswith("optimised_portfolio_"):
        data = pd.read_csv(path, usecols=usecols)
        return data, len(data)

    retained: list[pd.DataFrame] = []
    row_count = 0
    for chunk in pd.read_csv(path, usecols=usecols, chunksize=10_000):
        row_count += len(chunk)
        target = pd.to_numeric(chunk.get("target_weight", pd.Series(0.0, index=chunk.index)), errors="coerce").fillna(0.0)
        current = pd.to_numeric(chunk.get("current_weight", pd.Series(0.0, index=chunk.index)), errors="coerce").fillna(0.0)
        active = target.abs().gt(1e-12) | current.abs().gt(1e-12)
        if active.any():
            retained.append(chunk.loc[active].copy())
    data = pd.concat(retained, ignore_index=True) if retained else pd.DataFrame(columns=usecols)
    return data, row_count


def safe_read_csv(path: Path, source_name: str) -> tuple[pd.DataFrame, ReportSource]:
    if not path.exists():
        return (
            pd.DataFrame(),
            ReportSource(source_name, path, False, 0, None, None, "Source file is unavailable."),
        )
    try:
        if path.stat().st_size > _LARGE_SOURCE_BYTES:
            data, source_row_count = _read_large_reporting_csv(path, source_name)
        else:
            data = pd.read_csv(path)
            source_row_count = len(data)
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return (
            canonicalise_dataframe(data),
            ReportSource(source_name, path, True, source_row_count, modified_at, calculate_file_hash(path)),
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
    return pd.Timestamp.now('UTC').strftime("ic-%Y%m%d%H%M%S")


def _as_of_date(sources: list[ReportSource]) -> pd.Timestamp:
    available_dates = [source.modified_at for source in sources if source.modified_at is not None]
    if not available_dates:
        return pd.Timestamp.now('UTC')
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
