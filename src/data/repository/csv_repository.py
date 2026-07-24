from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd


class CSVRepository:
    """Repository backed by CSV files, preserving legacy fallback behaviour."""

    def __init__(self, root: str | Path = "reports/outputs", output_root: str | Path | None = None) -> None:
        self.root = Path(output_root) if output_root is not None else Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self.root / (name if name.endswith(".csv") else f"{name}.csv")

    def read_table(self, name: str) -> pd.DataFrame:
        path = self._path(name)
        return pd.read_csv(path) if path.exists() else pd.DataFrame()

    def write_table(self, name: str, frame: pd.DataFrame, primary_key: tuple[str, ...] | None = None) -> None:
        del primary_key
        frame.to_csv(self._path(name), index=False)

    def _save_dataset(self, name: str, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        clean = data.copy()
        if ingestion_run_id is not None:
            clean["ingestion_run_id"] = ingestion_run_id
        self.write_table(name, clean)

    def save_prices(self, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        self._save_dataset("prices_daily_sample", data, ingestion_run_id)

    def save_fundamentals(self, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        self._save_dataset("fundamentals_reported_sample", data, ingestion_run_id)

    def save_dividends(self, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        self._save_dataset("dividends_sample", data, ingestion_run_id)

    def save_fx_rates(self, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        self._save_dataset("fx_rates_sample", data, ingestion_run_id)

    def save_macro_observations(self, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        self._save_dataset("macro_observations_sample", data, ingestion_run_id)

    def save_news_documents(self, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        self._save_dataset("news_documents_sample", data, ingestion_run_id)

    def load_prices(self, security_ids: list[str], start_date: date, end_date: date) -> pd.DataFrame:
        data = self.read_table("prices_daily_sample")
        if data.empty:
            data = self.read_table("prices_daily")
        if data.empty:
            return pd.DataFrame()
        id_column = "security_id" if "security_id" in data else "ticker"
        date_column = "trade_date" if "trade_date" in data else "date"
        data[date_column] = pd.to_datetime(data[date_column])
        mask = data[id_column].astype(str).str.upper().isin([sid.upper() for sid in security_ids]) & data[date_column].between(
            pd.Timestamp(start_date), pd.Timestamp(end_date)
        )
        return data.loc[mask].copy()

    def load_point_in_time_fundamentals(self, security_ids: list[str], as_of_date: datetime) -> pd.DataFrame:
        data = self.read_table("fundamentals_reported_sample")
        if data.empty:
            data = self.read_table("stock_scorecard")
        if data.empty:
            return pd.DataFrame()
        id_column = "security_id" if "security_id" in data else "ticker"
        data = data[data[id_column].astype(str).str.upper().isin([sid.upper() for sid in security_ids])].copy()
        if "available_from" in data:
            data["available_from"] = pd.to_datetime(data["available_from"])
            data = data[data["available_from"] <= pd.Timestamp(as_of_date)]
        return data

    def load_point_in_time_macro(self, series_ids: list[str], as_of_date: datetime) -> pd.DataFrame:
        data = self.read_table("macro_observations_sample")
        if data.empty:
            return pd.DataFrame()
        data = data[data["series_id"].astype(str).isin(series_ids)].copy()
        if "available_from" in data:
            data["available_from"] = pd.to_datetime(data["available_from"])
            data = data[data["available_from"] <= pd.Timestamp(as_of_date)]
        return data

    def load_feature_snapshot(self, as_of_date: date) -> pd.DataFrame:
        data = self.read_table("features_monthly")
        if data.empty:
            data = self.read_table("feature_snapshots_monthly")
        if data.empty or "as_of_date" not in data:
            return data
        data["as_of_date"] = pd.to_datetime(data["as_of_date"]).dt.date
        return data[data["as_of_date"].eq(as_of_date)].copy()

    def register_model_run(self, metadata: dict[str, object]) -> str:
        model_run_id = str(metadata.get("model_run_id") or uuid4())
        row = {"model_run_id": model_run_id, **metadata}
        existing = self.read_table("model_runs")
        updated = pd.concat([existing, pd.DataFrame([row])], ignore_index=True) if not existing.empty else pd.DataFrame([row])
        self.write_table("model_runs", updated)
        return model_run_id

    def complete_model_run(
        self,
        model_run_id: str,
        status: str,
        output_path: str | None = None,
        error_message: str | None = None,
    ) -> None:
        data = self.read_table("model_runs")
        if data.empty or "model_run_id" not in data:
            return
        mask = data["model_run_id"].astype(str).eq(model_run_id)
        data.loc[mask, "status"] = status
        data.loc[mask, "completed_at"] = pd.Timestamp.utcnow().tz_localize(None)
        data.loc[mask, "output_path"] = output_path
        data.loc[mask, "error_message"] = error_message
        self.write_table("model_runs", data)
