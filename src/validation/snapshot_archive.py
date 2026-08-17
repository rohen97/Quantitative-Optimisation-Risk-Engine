from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DuckDBRepository
from src.data.schemas import SCHEMAS


FEATURE_COLUMNS = (
    "revenue_growth",
    "ebitda_margin",
    "net_income_margin",
    "free_cash_flow_yield",
    "fcf_stability",
    "cfo_to_net_income",
    "net_debt_to_ebitda",
    "interest_coverage",
    "roe",
    "roic",
    "pe_ratio",
    "pb_ratio",
    "ev_ebitda",
    "dividend_yield",
    "momentum_6m",
    "annualised_volatility",
    "downside_volatility",
    "liquidity_score",
    "sentiment_alt_data_score",
    "regime_suitability_score",
    "forecast_uncertainty_score",
)

FORECAST_METRICS = (
    "expected_total_return",
    "expected_volatility",
    "p5_return",
    "p50_return",
    "p95_return",
    "var_5",
    "cvar_5",
    "forecast_uncertainty_score",
)

SCORECARD_METRICS = (
    "final_recommendation_score",
    "scorecard_score",
    "cashflow_quality_score",
    "valuation_score",
    "risk_score",
    "portfolio_fit_score",
)


@dataclass(frozen=True)
class SnapshotArchiveResult:
    decision_dates: int
    manifests: int
    feature_rows: int
    forecast_rows: int
    scorecard_rows: int
    portfolio_rows: int


def _frame_hash(frame: pd.DataFrame, sort_by: tuple[str, ...]) -> str:
    if frame.empty:
        return hashlib.sha256(b"[]").hexdigest()
    ordered_columns = sorted(frame.columns)
    data = frame.loc[:, ordered_columns].copy()
    keys = [column for column in sort_by if column in data.columns]
    if keys:
        data = data.sort_values(keys, kind="mergesort", na_position="last")
    payload = data.to_json(
        orient="split",
        date_format="iso",
        date_unit="us",
        double_precision=15,
        default_handler=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _tree_hash(root: Path, patterns: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    paths: set[Path] = set()
    for pattern in patterns:
        paths.update(path for path in root.glob(pattern) if path.is_file())
    for path in sorted(paths):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _git_commit(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _base_security_rows(weights: pd.DataFrame) -> pd.DataFrame:
    if weights.empty:
        return weights.copy()
    preferred = weights.loc[weights["strategy"].eq("equal_weight_eligible")]
    if preferred.empty:
        preferred = weights
    return preferred.sort_values("security_id").drop_duplicates("security_id", keep="last")


def _numeric_snapshot(
    frame: pd.DataFrame,
    value_columns: tuple[str, ...],
    name_column: str,
    value_column: str,
) -> pd.DataFrame:
    columns = [column for column in value_columns if column in frame.columns]
    if frame.empty or not columns:
        return pd.DataFrame(columns=["security_id", name_column, value_column])
    result = frame[["security_id", *columns]].melt(
        id_vars="security_id",
        var_name=name_column,
        value_name=value_column,
    )
    result[value_column] = pd.to_numeric(result[value_column], errors="coerce")
    return result.loc[np.isfinite(result[value_column])].reset_index(drop=True)


def archive_walk_forward_snapshots(
    artifact_directory: str | Path,
    repository: DuckDBRepository | None = None,
    project_root: str | Path | None = None,
    write_detail_tables: bool = True,
) -> SnapshotArchiveResult:
    output = Path(artifact_directory)
    root = Path(project_root) if project_root is not None else Path(__file__).resolve().parents[2]
    weights = pd.read_parquet(output / "historical_portfolio_weights.parquet")
    forecasts = pd.read_parquet(output / "historical_forecasts.parquet")
    if weights.empty:
        raise ValueError("Cannot archive an empty historical portfolio-weight artifact.")

    weights["as_of_date"] = pd.to_datetime(weights["as_of_date"]).dt.normalize()
    forecasts["as_of_date"] = pd.to_datetime(forecasts["as_of_date"]).dt.normalize()
    now = pd.Timestamp.now("UTC").tz_localize(None)
    config_hash = _tree_hash(root, ("configs/**/*.yaml", "configs/**/*.yml"))
    source_hash = _tree_hash(root, ("src/**/*.py", "scripts/**/*.py"))
    git_commit = _git_commit(root)
    repo = repository
    if repo is None:
        data_config = load_data_config(root / "configs" / "data.yaml")
        repo = DuckDBRepository(data_config.duckdb_path)
        repo.execute_migrations(data_config.migrations_path)

    manifests: list[dict[str, object]] = []
    feature_parts: list[pd.DataFrame] = []
    forecast_parts: list[pd.DataFrame] = []
    scorecard_parts: list[pd.DataFrame] = []
    portfolio_parts: list[pd.DataFrame] = []
    decision_parts: list[pd.DataFrame] = []
    model_dates: list[dict[str, object]] = []

    for anchor in sorted(weights["as_of_date"].dropna().unique()):
        as_of = pd.Timestamp(anchor).normalize()
        anchor_weights = weights.loc[weights["as_of_date"].eq(as_of)].copy()
        anchor_forecasts = forecasts.loc[forecasts["as_of_date"].eq(as_of)].copy()
        base = _base_security_rows(anchor_weights)

        universe_hash = _frame_hash(base[["security_id"]], ("security_id",))
        feature_hash = _frame_hash(
            base[["security_id", *[c for c in FEATURE_COLUMNS if c in base.columns]]],
            ("security_id",),
        )
        forecast_hash = _frame_hash(
            anchor_forecasts,
            ("security_id", "horizon", "metric_name"),
        )
        ranking_columns = [
            column
            for column in (
                "security_id",
                "final_recommendation_score",
                "recommendation",
                "passes_hard_filters",
                "eligible_for_optimisation",
            )
            if column in base.columns
        ]
        ranking_hash = _frame_hash(base[ranking_columns], ("security_id",))
        portfolio_hash = _frame_hash(
            anchor_weights[["security_id", "strategy", "weight"]],
            ("strategy", "security_id"),
        )
        run_seed = "|".join(
            (as_of.date().isoformat(), universe_hash, feature_hash, forecast_hash, ranking_hash, portfolio_hash, config_hash, source_hash)
        )
        run_digest = hashlib.sha256(run_seed.encode("utf-8")).hexdigest()
        model_run_id = f"walk-forward-{as_of:%Y%m%d}-{run_digest[:12]}"
        forecast_versions = anchor_forecasts.get("model_version", pd.Series(dtype=str)).dropna()
        base_version = str(forecast_versions.iloc[0]) if not forecast_versions.empty else "wolf_walk_forward_v1"

        manifests.append(
            {
                "model_run_id": model_run_id,
                "as_of_date": as_of.date(),
                "model_name": "Wolf Quant Model walk-forward",
                "model_version": f"{base_version}+src.{source_hash[:12]}",
                "git_commit_hash": git_commit,
                "eligible_universe_hash": universe_hash,
                "feature_snapshot_hash": feature_hash,
                "forecast_snapshot_hash": forecast_hash,
                "ranking_snapshot_hash": ranking_hash,
                "portfolio_snapshot_hash": portfolio_hash,
                "config_hash": config_hash,
                "archive_path": output.as_posix(),
                "available_from": now,
                "retrieved_at": now,
                "source": "retrospective_walk_forward_archive",
            }
        )
        model_dates.append({"as_of_date": as_of.date()})
        decision_parts.append(
            base[["security_id"]].assign(as_of_date=as_of.date())
        )

        if not write_detail_tables:
            continue

        features = _numeric_snapshot(base, FEATURE_COLUMNS, "feature_name", "feature_value")
        if not features.empty:
            features = features.assign(
                model_run_id=model_run_id,
                as_of_date=as_of.date(),
                feature_text_value=None,
                feature_version=f"walk_forward_archive_{source_hash[:12]}",
                calculated_at=now,
            )
            feature_parts.append(features.loc[:, SCHEMAS["feature_snapshots_monthly"].column_names])

        forecast_metrics = _numeric_snapshot(
            anchor_forecasts,
            FORECAST_METRICS,
            "metric_name",
            "metric_value",
        )
        if not forecast_metrics.empty:
            horizons = anchor_forecasts[["security_id", "horizon"]].reset_index(drop=True)
            repeated_horizons = np.tile(horizons["horizon"].to_numpy(), len([c for c in FORECAST_METRICS if c in anchor_forecasts.columns]))
            forecast_metrics["horizon"] = repeated_horizons
            forecast_metrics = forecast_metrics.assign(model_run_id=model_run_id, as_of_date=as_of.date())
            forecast_parts.append(
                forecast_metrics.loc[:, SCHEMAS["distributional_forecast_snapshots"].column_names]
            )

        scores = _numeric_snapshot(base, SCORECARD_METRICS, "score_name", "score_value")
        if not scores.empty:
            scores = scores.assign(model_run_id=model_run_id, as_of_date=as_of.date())
            scorecard_parts.append(scores.loc[:, SCHEMAS["scorecard_snapshots"].column_names])

        portfolio = anchor_weights[["strategy", "security_id", "weight"]].rename(
            columns={"strategy": "portfolio_name"}
        )
        recommendation_column = next(
            (column for column in ("final_recommendation", "recommendation") if column in anchor_weights.columns),
            None,
        )
        portfolio["model_run_id"] = model_run_id
        portfolio["as_of_date"] = as_of.date()
        portfolio["market_value_usd"] = np.nan
        portfolio["recommendation"] = (
            anchor_weights[recommendation_column].to_numpy() if recommendation_column else None
        )
        portfolio_parts.append(portfolio.loc[:, SCHEMAS["portfolio_weight_snapshots"].column_names])

    manifest_frame = pd.DataFrame(manifests, columns=SCHEMAS["decision_snapshot_manifests"].column_names)
    repo.write_table(
        "decision_snapshot_manifests",
        manifest_frame,
        SCHEMAS["decision_snapshot_manifests"].primary_key,
    )
    decision_frame = pd.concat(decision_parts, ignore_index=True).drop_duplicates()
    repo.write_table("decision_dates", decision_frame, ("security_id", "as_of_date"))
    model_date_frame = pd.DataFrame(model_dates).drop_duplicates()
    repo.write_table("model_decision_dates", model_date_frame, ("as_of_date",))

    def write_parts(table: str, parts: list[pd.DataFrame]) -> int:
        if not parts:
            return 0
        frame = pd.concat(parts, ignore_index=True)
        repo.write_table(table, frame, SCHEMAS[table].primary_key)
        return len(frame)

    feature_count = write_parts("feature_snapshots_monthly", feature_parts)
    forecast_count = write_parts("distributional_forecast_snapshots", forecast_parts)
    scorecard_count = write_parts("scorecard_snapshots", scorecard_parts)
    portfolio_count = write_parts("portfolio_weight_snapshots", portfolio_parts)
    return SnapshotArchiveResult(
        decision_dates=len(model_date_frame),
        manifests=len(manifest_frame),
        feature_rows=feature_count,
        forecast_rows=forecast_count,
        scorecard_rows=scorecard_count,
        portfolio_rows=portfolio_count,
    )
