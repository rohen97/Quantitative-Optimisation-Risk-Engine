from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.utils.config import ROOT
from src.validation.models import ValidationDataPackage, ValidationIssue


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _read_parquet(path: Path) -> pd.DataFrame:
    try:
        return pd.read_parquet(path) if path.exists() else pd.DataFrame()
    except (ImportError, OSError, ValueError):
        return pd.DataFrame()


def load_validation_data(validation_run_id: str, as_of_date: pd.Timestamp, output_root: Path | None = None) -> ValidationDataPackage:
    outputs = output_root or ROOT / "reports" / "outputs"
    forecasts: dict[str, pd.DataFrame] = {}
    for horizon in ("3M", "6M", "9M", "12M"):
        frame = _read_csv(outputs / f"ml_forecasts_{horizon.lower()}.csv")
        if not frame.empty:
            frame["forecast_date"] = pd.to_datetime(frame.get("as_of_date", as_of_date))
            frame["horizon"] = horizon
            forecasts[horizon] = frame
    price_history = _read_parquet(ROOT / "data" / "parquet" / "prices_daily" / "data.parquet")
    realised = pd.DataFrame()
    if not price_history.empty:
        rename = {"ticker": "security_id", "date": "date", "return": "return"}
        realised = price_history.rename(columns=rename)
        expected = {"security_id", "date", "return"}
        realised = realised[list(expected)] if expected.issubset(realised) else pd.DataFrame()
    portfolios = {
        "selected_classical": _read_csv(outputs / "proposed_portfolio.csv"),
        "drl": _read_csv(outputs / "drl_challenger_portfolio.csv"),
        "final_portfolio": _read_csv(outputs / "final_recommendations.csv"),
        "current_portfolio": _read_csv(outputs / "current_portfolio_enriched.csv"),
    }
    issues: list[ValidationIssue] = []
    if not forecasts:
        issues.append(ValidationIssue("forecasts", "warning", "missing_forecasts", "No forecast snapshots were available."))
    if realised.empty:
        issues.append(ValidationIssue("outcomes", "warning", "missing_realised_returns", "No realised return history was available."))
    return ValidationDataPackage(
        validation_run_id=validation_run_id,
        as_of_date=as_of_date,
        forecasts=forecasts,
        realised_returns=realised,
        risk_forecasts=_read_csv(outputs / "return_distribution_forecasts.csv"),
        portfolio_weights=portfolios,
        portfolio_returns=_read_csv(outputs / "drl_backtest_results.csv"),
        transaction_costs=_read_csv(outputs / "drl_trade_list.csv"),
        regime_history=pd.concat(
            [_read_csv(outputs / "factor_regime_probabilities.csv"), _read_csv(outputs / "chaos_regime_probabilities.csv")],
            axis=1,
        ),
        drl_seed_results=_read_csv(outputs / "drl_seed_results.csv"),
        drl_benchmark_results=_read_csv(outputs / "drl_benchmark_comparison.csv"),
        constraint_reports={"classical": _read_csv(outputs / "portfolio_constraint_report.csv")},
        lineage=_read_csv(outputs / "model_run_lineage.csv"),
        issues=issues,
    )
