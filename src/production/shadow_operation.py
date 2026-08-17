from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Mapping

import numpy as np
import pandas as pd

from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DuckDBRepository
from src.utils.config import ROOT, load_yaml


SHADOW_PORTFOLIO_FILES = {
    "selected_final": ("final_portfolio_weights.csv", ("final_weight", "target_weight")),
    "classical_cvar": ("optimised_portfolio_cvar_constrained.csv", ("target_weight",)),
    "classical_regional_alpha": ("optimised_portfolio_regional_alpha.csv", ("target_weight",)),
    "supervised_alpha_governed": (
        "supervised_alpha/optimised_portfolio_supervised_alpha.csv",
        ("target_weight",),
    ),
    "drl_projected": ("drl_target_weights.csv", ("target_weight",)),
}


def repository_model_version(repository_root: Path = ROOT) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        value = result.stdout.strip()
        if result.returncode == 0 and value:
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repository_root,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return f"{value}-dirty" if status.stdout.strip() else value
    except (OSError, subprocess.SubprocessError):
        pass
    return "working-tree-unversioned"


def _weight_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str:
    for column in candidates:
        if column in frame:
            return column
    raise ValueError(f"No portfolio weight column found among {candidates}.")


def normalise_shadow_portfolio(
    frame: pd.DataFrame,
    weight_columns: tuple[str, ...],
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["security_id", "target_weight", "currency"])
    weight_column = _weight_column(frame, weight_columns)
    security = frame.get("security_id", frame.get("ticker"))
    if security is None:
        raise ValueError("Shadow portfolio requires security_id or ticker.")
    clean = pd.DataFrame(
        {
            "security_id": security.astype(str),
            "target_weight": pd.to_numeric(frame[weight_column], errors="coerce"),
            "currency": frame.get("currency", pd.Series("USD", index=frame.index)),
        }
    ).dropna(subset=["security_id", "target_weight"])
    clean = clean.loc[clean["target_weight"].gt(1.0e-12)].copy()
    if clean["target_weight"].lt(-1.0e-12).any():
        raise ValueError("Shadow portfolios must be long-only.")
    clean = clean.groupby("security_id", as_index=False).agg(
        target_weight=("target_weight", "sum"),
        currency=("currency", "first"),
    )
    total = float(clean["target_weight"].sum())
    if total <= 0 or total > 1.0 + 1.0e-6:
        raise ValueError(f"Invalid shadow portfolio weight sum: {total:.8f}.")
    if total < 1.0 - 1.0e-8:
        clean = pd.concat(
            [
                clean,
                pd.DataFrame(
                    [{"security_id": "CASH", "target_weight": 1.0 - total, "currency": "USD"}]
                ),
            ],
            ignore_index=True,
        )
    elif total != 1.0:
        clean["target_weight"] /= total
    return clean.sort_values("security_id").reset_index(drop=True)


def build_shadow_portfolios(output_directory: Path) -> dict[str, pd.DataFrame]:
    portfolios: dict[str, pd.DataFrame] = {}
    for name, (filename, weight_columns) in SHADOW_PORTFOLIO_FILES.items():
        path = output_directory / filename
        if path.exists():
            portfolios[name] = normalise_shadow_portfolio(
                pd.read_csv(path),
                weight_columns,
            )

    scorecard_path = output_directory / "stock_scorecard.csv"
    if scorecard_path.exists():
        scorecard = pd.read_csv(scorecard_path)
        eligible = scorecard.loc[
            scorecard.get(
                "passes_hard_filters",
                pd.Series(False, index=scorecard.index),
            ).fillna(False).astype(bool)
        ].copy()
        if "issuer_id" in eligible:
            eligible = eligible.sort_values(
                ["final_recommendation_score", "ticker"],
                ascending=[False, True],
                kind="stable",
            ).drop_duplicates("issuer_id")
        if not eligible.empty:
            equal = eligible.copy()
            equal["_shadow_weight"] = 1.0 / len(equal)
            portfolios["equal_weight_eligible"] = normalise_shadow_portfolio(
                equal,
                ("_shadow_weight",),
            )
            cap = eligible.copy()
            cap_values = pd.to_numeric(cap.get("market_cap_usd"), errors="coerce").fillna(0.0).clip(lower=0.0)
            if float(cap_values.sum()) > 0:
                cap["_shadow_weight"] = cap_values / cap_values.sum()
                portfolios["cap_weight_eligible"] = normalise_shadow_portfolio(
                    cap,
                    ("_shadow_weight",),
                )
    return portfolios


def _portfolio_hash(portfolio: pd.DataFrame) -> str:
    payload = "\n".join(
        f"{row.security_id}|{float(row.target_weight):.12f}"
        for row in portfolio.sort_values("security_id").itertuples(index=False)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _portfolio_bundle_hash(portfolios: Mapping[str, pd.DataFrame]) -> str:
    payload = "\n".join(
        f"{name}|{_portfolio_hash(portfolios[name])}"
        for name in sorted(portfolios)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _decision_prices(
    repository: DuckDBRepository,
    security_ids: list[str],
    as_of_date: pd.Timestamp,
    lookback_days: int = 14,
) -> pd.DataFrame:
    requested = [value for value in security_ids if value.upper() != "CASH"]
    if not requested:
        return pd.DataFrame(columns=["security_id", "decision_trade_date", "decision_price"])
    return repository.query(
        """
        SELECT security_id,
               trade_date AS decision_trade_date,
               COALESCE(adjusted_close, close_price) AS decision_price
        FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY security_id
                ORDER BY trade_date DESC,
                         CASE WHEN source = 'bloomberg' THEN 1
                              WHEN source = 'yfinance' THEN 2
                              WHEN source = 'eodhd' THEN 3
                              ELSE 4 END,
                         retrieved_at DESC
            ) AS price_row
            FROM prices_daily
            WHERE security_id IN (SELECT UNNEST(?))
              AND trade_date BETWEEN ? AND ?
              AND COALESCE(adjusted_close, close_price) > 0
        )
        WHERE price_row = 1
        """,
        [
            requested,
            (as_of_date - pd.Timedelta(days=lookback_days)).date(),
            as_of_date.date(),
        ],
    )


def _weight_distance(left: pd.DataFrame, right: pd.DataFrame) -> tuple[float, float]:
    left_weights = left.set_index("security_id")["target_weight"]
    right_weights = right.set_index("security_id")["target_weight"]
    index = left_weights.index.union(right_weights.index)
    l1 = float(
        (
            left_weights.reindex(index, fill_value=0.0)
            - right_weights.reindex(index, fill_value=0.0)
        ).abs().sum()
    )
    left_names = set(left_weights.loc[left_weights.gt(1.0e-12)].index) - {"CASH"}
    right_names = set(right_weights.loc[right_weights.gt(1.0e-12)].index) - {"CASH"}
    union = left_names | right_names
    overlap = len(left_names & right_names) / len(union) if union else 1.0
    return l1, float(overlap)


def _previous_cycle_weights(
    repository: DuckDBRepository,
    as_of_date: pd.Timestamp,
    portfolio_name: str,
) -> tuple[str | None, pd.DataFrame]:
    prior = repository.query(
        """
        SELECT cycle_id
        FROM model_shadow_cycles
        WHERE as_of_date < ?
        ORDER BY as_of_date DESC, recorded_at DESC
        LIMIT 1
        """,
        [as_of_date.date()],
    )
    if prior.empty:
        return None, pd.DataFrame()
    cycle_id = str(prior.iloc[0]["cycle_id"])
    weights = repository.query(
        """
        SELECT security_id, target_weight, currency
        FROM model_shadow_cycle_weights
        WHERE cycle_id = ? AND portfolio_name = ?
        ORDER BY security_id
        """,
        [cycle_id, portfolio_name],
    )
    return cycle_id, weights


def record_shadow_cycle(
    repository: DuckDBRepository,
    portfolios: Mapping[str, pd.DataFrame],
    *,
    as_of_date: pd.Timestamp,
    recorded_at: pd.Timestamp | None = None,
    production_run_id: str | None = None,
    model_version: str = "working-tree-unversioned",
    selected_source: str = "baseline_optimiser",
    governance_status: str = "CONDITIONALLY_APPROVED",
    maximum_recording_lag_days: int = 7,
    prospective_start_date: str | pd.Timestamp | None = None,
    cost_bps: float = 17.5,
) -> str:
    if "selected_final" not in portfolios:
        raise ValueError("Shadow operation requires selected_final weights.")
    decision_date = pd.Timestamp(as_of_date).normalize()
    observed_at = pd.Timestamp(recorded_at or datetime.now(UTC)).tz_localize(None)
    lag_days = (observed_at.normalize() - decision_date).days
    prospective_start = (
        pd.Timestamp(prospective_start_date).normalize()
        if prospective_start_date is not None
        else None
    )
    prospective = (
        0 <= lag_days <= int(maximum_recording_lag_days)
        and (prospective_start is None or decision_date >= prospective_start)
    )
    cycle_id = f"shadow-{decision_date.date().isoformat()}"
    normalised = {
        name: normalise_shadow_portfolio(frame, ("target_weight",))
        for name, frame in portfolios.items()
        if not frame.empty
    }
    selected = normalised["selected_final"]
    selected_hash = _portfolio_hash(selected)
    bundle_hash = _portfolio_bundle_hash(normalised)

    prior_cycle_id, prior_selected = _previous_cycle_weights(
        repository,
        decision_date,
        "selected_final",
    )
    if prior_selected.empty:
        risky_weight = float(
            selected.loc[selected["security_id"].ne("CASH"), "target_weight"].sum()
        )
        selected_l1 = 2.0 * risky_weight
        overlap = 0.0
    else:
        selected_l1, overlap = _weight_distance(selected, prior_selected)
    turnover = 0.5 * selected_l1
    estimated_cost = turnover * float(cost_bps) / 10_000.0

    all_ids = sorted(
        {
            security_id
            for frame in normalised.values()
            for security_id in frame["security_id"].astype(str)
        }
    )
    prices = _decision_prices(repository, all_ids, decision_date)
    weight_rows: list[pd.DataFrame] = []
    for name, frame in normalised.items():
        dated = frame.copy()
        dated.insert(0, "portfolio_name", name)
        dated.insert(0, "cycle_id", cycle_id)
        if not prices.empty:
            dated = dated.merge(
                prices,
                on="security_id",
                how="left",
            )
        else:
            dated["decision_trade_date"] = pd.NaT
            dated["decision_price"] = np.nan
        cash = dated["security_id"].eq("CASH")
        dated.loc[cash, "decision_trade_date"] = decision_date
        dated.loc[cash, "decision_price"] = 1.0
        weight_rows.append(dated)
    weights = pd.concat(weight_rows, ignore_index=True)
    cycle = pd.DataFrame(
        [
            {
                "cycle_id": cycle_id,
                "as_of_date": decision_date,
                "recorded_at": observed_at,
                "production_run_id": production_run_id,
                "model_version": model_version,
                "selected_source": selected_source,
                "governance_status": governance_status,
                "selected_portfolio_hash": selected_hash,
                "portfolio_bundle_hash": bundle_hash,
                "evaluation_due_date": decision_date + pd.DateOffset(months=1),
                "evaluation_status": "pending",
                "prospective_eligible": prospective,
                "prior_cycle_id": prior_cycle_id,
                "selected_weight_l1_change": selected_l1,
                "selected_name_overlap": overlap,
                "estimated_turnover": turnover,
                "estimated_cost_fraction": estimated_cost,
                "evaluated_at": pd.NaT,
                "active_return_vs_equal_weight": np.nan,
                "realised_slippage_bps": np.nan,
                "notes": "Outcomes remain unavailable until the evaluation due date.",
            }
        ]
    )

    with repository.connection() as connection:
        existing = connection.execute(
            """
            SELECT selected_portfolio_hash, portfolio_bundle_hash
            FROM model_shadow_cycles
            WHERE cycle_id = ?
            """,
            [cycle_id],
        ).fetchone()
        if existing is not None:
            frozen_bundle_hash = existing[1]
            if frozen_bundle_hash is None or not str(frozen_bundle_hash).strip():
                frozen_weights = connection.execute(
                    """
                    SELECT portfolio_name, security_id, target_weight, currency
                    FROM model_shadow_cycle_weights
                    WHERE cycle_id = ?
                    ORDER BY portfolio_name, security_id
                    """,
                    [cycle_id],
                ).fetchdf()
                frozen_portfolios = {
                    str(name): group[["security_id", "target_weight", "currency"]]
                    .copy()
                    .reset_index(drop=True)
                    for name, group in frozen_weights.groupby(
                        "portfolio_name",
                        sort=True,
                    )
                }
                frozen_bundle_hash = _portfolio_bundle_hash(frozen_portfolios)
                connection.execute(
                    """
                    UPDATE model_shadow_cycles
                    SET portfolio_bundle_hash = ?
                    WHERE cycle_id = ? AND portfolio_bundle_hash IS NULL
                    """,
                    [frozen_bundle_hash, cycle_id],
                )
            if str(existing[0]) != selected_hash or str(frozen_bundle_hash) != bundle_hash:
                raise RuntimeError(
                    f"Shadow cycle {cycle_id} is already frozen with a different portfolio bundle."
                )
            return cycle_id
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.register("_shadow_cycle", cycle)
            connection.register("_shadow_weights", weights)
            connection.execute(
                "INSERT INTO model_shadow_cycles BY NAME SELECT * FROM _shadow_cycle"
            )
            connection.execute(
                "INSERT INTO model_shadow_cycle_weights BY NAME SELECT * FROM _shadow_weights"
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.unregister("_shadow_cycle")
            connection.unregister("_shadow_weights")
    return cycle_id


def _ending_prices(
    repository: DuckDBRepository,
    security_ids: list[str],
    due_date: pd.Timestamp,
    tolerance_days: int,
) -> pd.DataFrame:
    requested = [value for value in security_ids if value.upper() != "CASH"]
    if not requested:
        return pd.DataFrame(columns=["security_id", "ending_trade_date", "ending_price"])
    return repository.query(
        """
        SELECT security_id,
               trade_date AS ending_trade_date,
               COALESCE(adjusted_close, close_price) AS ending_price
        FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY security_id
                ORDER BY trade_date ASC,
                         CASE WHEN source = 'bloomberg' THEN 1
                              WHEN source = 'yfinance' THEN 2
                              WHEN source = 'eodhd' THEN 3
                              ELSE 4 END,
                         retrieved_at DESC
            ) AS price_row
            FROM prices_daily
            WHERE security_id IN (SELECT UNNEST(?))
              AND trade_date BETWEEN ? AND ?
              AND COALESCE(adjusted_close, close_price) > 0
        )
        WHERE price_row = 1
        """,
        [requested, due_date.date(), (due_date + pd.Timedelta(days=tolerance_days)).date()],
    )


def _portfolio_turnover(
    repository: DuckDBRepository,
    cycle: pd.Series,
    portfolio_name: str,
    weights: pd.DataFrame,
) -> float:
    prior_cycle = cycle.get("prior_cycle_id")
    if prior_cycle is None or pd.isna(prior_cycle) or not str(prior_cycle).strip():
        return float(weights.loc[weights["security_id"].ne("CASH"), "target_weight"].sum())
    prior = repository.query(
        """
        SELECT security_id, target_weight, currency
        FROM model_shadow_cycle_weights
        WHERE cycle_id = ? AND portfolio_name = ?
        """,
        [str(prior_cycle), portfolio_name],
    )
    if prior.empty:
        return float(weights.loc[weights["security_id"].ne("CASH"), "target_weight"].sum())
    l1, _ = _weight_distance(weights, prior)
    return 0.5 * l1


def evaluate_pending_shadow_cycles(
    repository: DuckDBRepository,
    *,
    evaluation_as_of: pd.Timestamp | None = None,
    price_tolerance_days: int = 14,
    minimum_valid_weight: float = 0.90,
    cost_bps: float = 17.5,
) -> int:
    evaluation_date = pd.Timestamp(evaluation_as_of or datetime.now(UTC)).tz_localize(None).normalize()
    pending = repository.query(
        """
        SELECT *
        FROM model_shadow_cycles
        WHERE evaluation_status = 'pending'
          AND evaluation_due_date <= ?
        ORDER BY as_of_date
        """,
        [evaluation_date.date()],
    )
    completed = 0
    for cycle in pending.itertuples(index=False):
        cycle_series = pd.Series(cycle._asdict())
        weights = repository.query(
            """
            SELECT *
            FROM model_shadow_cycle_weights
            WHERE cycle_id = ?
            ORDER BY portfolio_name, security_id
            """,
            [cycle.cycle_id],
        )
        endings = _ending_prices(
            repository,
            sorted(weights["security_id"].astype(str).unique()),
            pd.Timestamp(cycle.evaluation_due_date),
            price_tolerance_days,
        )
        result_rows = []
        for portfolio_name, group in weights.groupby("portfolio_name", sort=True):
            evaluated = group.merge(endings, on="security_id", how="left")
            cash = evaluated["security_id"].eq("CASH")
            evaluated.loc[cash, "ending_price"] = 1.0
            valid = (
                pd.to_numeric(evaluated["decision_price"], errors="coerce").gt(0)
                & pd.to_numeric(evaluated["ending_price"], errors="coerce").gt(0)
            )
            valid_weight = float(evaluated.loc[valid, "target_weight"].sum())
            missing = int((~valid & ~cash).sum())
            status = "completed" if valid_weight >= minimum_valid_weight else "insufficient_price_coverage"
            if valid_weight > 0:
                returns = (
                    pd.to_numeric(evaluated.loc[valid, "ending_price"], errors="coerce")
                    / pd.to_numeric(evaluated.loc[valid, "decision_price"], errors="coerce")
                    - 1.0
                )
                gross = float(
                    np.dot(
                        evaluated.loc[valid, "target_weight"].to_numpy(dtype=float),
                        returns.to_numpy(dtype=float),
                    )
                    / valid_weight
                )
            else:
                gross = np.nan
            turnover = _portfolio_turnover(
                repository,
                cycle_series,
                str(portfolio_name),
                group,
            )
            cost = turnover * float(cost_bps) / 10_000.0
            result_rows.append(
                {
                    "cycle_id": cycle.cycle_id,
                    "portfolio_name": str(portfolio_name),
                    "evaluated_at": datetime.now(UTC).replace(tzinfo=None),
                    "gross_return": gross,
                    "net_return": gross - cost if np.isfinite(gross) else np.nan,
                    "estimated_turnover": turnover,
                    "estimated_cost_fraction": cost,
                    "valid_weight": valid_weight,
                    "missing_security_count": missing,
                    "status": status,
                }
            )
        results = pd.DataFrame(result_rows)
        required = results.loc[
            results["portfolio_name"].isin(["selected_final", "equal_weight_eligible"])
        ]
        cycle_complete = (
            set(required["portfolio_name"]) == {"selected_final", "equal_weight_eligible"}
            and required["status"].eq("completed").all()
        )
        active_return = np.nan
        if cycle_complete:
            indexed = required.set_index("portfolio_name")
            active_return = float(
                indexed.loc["selected_final", "net_return"]
                - indexed.loc["equal_weight_eligible", "net_return"]
            )
        retry_window_open = evaluation_date <= (
            pd.Timestamp(cycle.evaluation_due_date)
            + pd.Timedelta(days=price_tolerance_days)
        )
        cycle_status = (
            "completed"
            if cycle_complete
            else "pending"
            if retry_window_open
            else "insufficient_price_coverage"
        )
        with repository.connection() as connection:
            connection.register("_shadow_results", results)
            try:
                connection.execute("BEGIN TRANSACTION")
                connection.execute(
                    "DELETE FROM model_shadow_cycle_results USING _shadow_results "
                    "WHERE model_shadow_cycle_results.cycle_id = _shadow_results.cycle_id "
                    "AND model_shadow_cycle_results.portfolio_name = _shadow_results.portfolio_name"
                )
                connection.execute(
                    "INSERT INTO model_shadow_cycle_results BY NAME SELECT * FROM _shadow_results"
                )
                connection.execute(
                    """
                    UPDATE model_shadow_cycles
                    SET evaluation_status = ?,
                        evaluated_at = ?,
                        active_return_vs_equal_weight = ?,
                        notes = ?
                    WHERE cycle_id = ?
                    """,
                    [
                        cycle_status,
                        datetime.now(UTC).replace(tzinfo=None),
                        active_return,
                        (
                            "Selected and equal-weight outcomes completed."
                            if cycle_complete
                            else "One or more required portfolios lacked sufficient price coverage."
                        ),
                        cycle.cycle_id,
                    ],
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
            finally:
                connection.unregister("_shadow_results")
        completed += int(cycle_complete)
    return completed


def completed_shadow_cycle_count(
    repository: DuckDBRepository,
    prospective_start: str | pd.Timestamp | None = None,
) -> int:
    try:
        if prospective_start is None:
            result = repository.query(
                """
                SELECT COUNT(*) AS cycles
                FROM model_shadow_cycles
                WHERE prospective_eligible
                  AND evaluation_status = 'completed'
                """
            )
        else:
            result = repository.query(
                """
                SELECT COUNT(*) AS cycles
                FROM model_shadow_cycles
                WHERE prospective_eligible
                  AND evaluation_status = 'completed'
                  AND as_of_date >= ?
                """,
                [pd.Timestamp(prospective_start).date()],
            )
    except Exception:
        return 0
    return int(result.iloc[0]["cycles"]) if not result.empty else 0


def backfill_shadow_bundle_hashes(repository: DuckDBRepository) -> int:
    """Derive bundle hashes for cycles recorded before bundle-level freezing."""

    pending = repository.query(
        """
        SELECT cycle_id
        FROM model_shadow_cycles
        WHERE portfolio_bundle_hash IS NULL OR TRIM(portfolio_bundle_hash) = ''
        ORDER BY cycle_id
        """
    )
    updated = 0
    for cycle_id in pending.get("cycle_id", pd.Series(dtype=str)).astype(str):
        weights = repository.query(
            """
            SELECT portfolio_name, security_id, target_weight, currency
            FROM model_shadow_cycle_weights
            WHERE cycle_id = ?
            ORDER BY portfolio_name, security_id
            """,
            [cycle_id],
        )
        if weights.empty:
            continue
        portfolios = {
            str(name): group[["security_id", "target_weight", "currency"]]
            .copy()
            .reset_index(drop=True)
            for name, group in weights.groupby("portfolio_name", sort=True)
        }
        with repository.connection() as connection:
            connection.execute(
                """
                UPDATE model_shadow_cycles
                SET portfolio_bundle_hash = ?
                WHERE cycle_id = ? AND portfolio_bundle_hash IS NULL
                """,
                [_portfolio_bundle_hash(portfolios), cycle_id],
            )
        updated += 1
    return updated


def write_shadow_report(
    repository: DuckDBRepository,
    output_directory: Path,
    required_cycles: int = 3,
    prospective_start_date: str | pd.Timestamp | None = None,
) -> tuple[Path, Path]:
    backfill_shadow_bundle_hashes(repository)
    prospective_start = (
        pd.Timestamp(prospective_start_date).normalize()
        if prospective_start_date is not None
        else None
    )
    if prospective_start is not None:
        with repository.connection() as connection:
            connection.execute(
                """
                UPDATE model_shadow_cycles
                SET prospective_eligible = FALSE
                WHERE as_of_date < ? AND prospective_eligible
                """,
                [prospective_start.date()],
            )
    cycles = repository.query(
        "SELECT * FROM model_shadow_cycles ORDER BY as_of_date, recorded_at"
    )
    results = repository.query(
        "SELECT * FROM model_shadow_cycle_results ORDER BY cycle_id, portfolio_name"
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    csv_path = output_directory / "shadow_cycle_summary.csv"
    json_path = output_directory / "shadow_operation_status.json"
    temporary_csv = csv_path.with_suffix(".csv.tmp")
    cycles.to_csv(temporary_csv, index=False)
    temporary_csv.replace(csv_path)
    completed_prospective = int(
        (
            cycles.get("prospective_eligible", pd.Series(False, index=cycles.index)).fillna(False).astype(bool)
            & cycles.get("evaluation_status", pd.Series("", index=cycles.index)).eq("completed")
            & (
                pd.to_datetime(cycles.get("as_of_date"), errors="coerce").ge(
                    prospective_start
                )
                if prospective_start is not None
                else pd.Series(True, index=cycles.index)
            )
        ).sum()
    )
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "required_prospective_cycles": int(required_cycles),
        "prospective_start_date": prospective_start,
        "completed_prospective_cycles": completed_prospective,
        "remaining_prospective_cycles": max(int(required_cycles) - completed_prospective, 0),
        "deployment_evidence_ready": completed_prospective >= int(required_cycles),
        "cycle_count": len(cycles),
        "result_count": len(results),
        "latest_cycle": cycles.iloc[-1].to_dict() if not cycles.empty else None,
    }
    temporary_json = json_path.with_suffix(".json.tmp")
    temporary_json.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temporary_json.replace(json_path)
    return csv_path, json_path


def run_shadow_operation_from_outputs(
    *,
    repository_root: Path = ROOT,
    output_directory: Path | None = None,
    as_of_date: pd.Timestamp | None = None,
    production_run_id: str | None = None,
    governance_status: str = "CONDITIONALLY_APPROVED",
    selected_source: str | None = None,
    maximum_recording_lag_days: int = 7,
    required_cycles: int = 3,
    prospective_start_date: str | pd.Timestamp | None = None,
) -> str:
    outputs = output_directory or repository_root / "reports" / "outputs"
    data_config = load_data_config()
    repository = DuckDBRepository(data_config.duckdb_path)
    repository.execute_migrations(repository_root / "sql" / "migrations")
    if prospective_start_date is None:
        shadow_config = (
            load_yaml("configs/production.yaml")
            .get("production", {})
            .get("shadow_operation", {})
        )
        prospective_start_date = shadow_config.get("prospective_start_date")
    evaluate_pending_shadow_cycles(repository, evaluation_as_of=as_of_date)
    portfolios = build_shadow_portfolios(outputs)
    if selected_source is None and "selected_final" in portfolios:
        selected_path = outputs / "final_portfolio_weights.csv"
        selected_frame = pd.read_csv(selected_path)
        source_series = selected_frame.get("final_selected_weights_source")
        selected_source = (
            str(source_series.dropna().iloc[0])
            if source_series is not None and not source_series.dropna().empty
            else "baseline_optimiser"
        )
    cycle_id = record_shadow_cycle(
        repository,
        portfolios,
        as_of_date=pd.Timestamp(as_of_date or datetime.now(UTC)).tz_localize(None),
        production_run_id=production_run_id,
        model_version=repository_model_version(repository_root),
        selected_source=selected_source or "baseline_optimiser",
        governance_status=governance_status,
        maximum_recording_lag_days=maximum_recording_lag_days,
        prospective_start_date=prospective_start_date,
    )
    write_shadow_report(
        repository,
        outputs / "shadow_operation",
        required_cycles=required_cycles,
        prospective_start_date=prospective_start_date,
    )
    return cycle_id
