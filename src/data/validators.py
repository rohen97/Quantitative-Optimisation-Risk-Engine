from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.schemas import TableSchema


VALID_CURRENCIES = {"USD", "GBP", "EUR", "CHF", "HKD", "CNY", "JPY", "CAD", "AUD", "SGD"}


@dataclass(frozen=True)
class ValidationIssue:
    dataset: str
    severity: str
    rule: str
    message: str
    affected_rows: int


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    issues: tuple[ValidationIssue, ...]

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([issue.__dict__ for issue in self.issues])


def _result(issues: list[ValidationIssue]) -> ValidationResult:
    return ValidationResult(valid=not any(issue.severity == "error" for issue in issues), issues=tuple(issues))


def _issue(dataset: str, rule: str, message: str, affected_rows: int, severity: str = "error") -> ValidationIssue:
    return ValidationIssue(dataset=dataset, severity=severity, rule=rule, message=message, affected_rows=int(affected_rows))


def save_validation_report(result: ValidationResult, output_path: str | Path = "reports/outputs/data_validation_report.csv") -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    result.to_frame().to_csv(path, index=False)
    return path


def validate_required_columns(frame: pd.DataFrame, required: list[str] | tuple[str, ...]) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def validate_finite_numeric(frame: pd.DataFrame, columns: list[str] | tuple[str, ...]) -> None:
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        if not np.isfinite(values.to_numpy(dtype=float)).all():
            raise ValueError(f"Column {column} contains non-finite values.")


def validate_schema(frame: pd.DataFrame, schema: TableSchema) -> None:
    validate_required_columns(frame, [column.name for column in schema.columns if not column.nullable])
    numeric = [column.name for column in schema.columns if column.dtype in {"DOUBLE", "INTEGER"} and column.name in frame]
    if numeric:
        validate_finite_numeric(frame.dropna(subset=numeric), numeric)


def validate_unique_key(frame: pd.DataFrame, key: tuple[str, ...]) -> None:
    validate_required_columns(frame, key)
    if frame.duplicated(list(key)).any():
        raise ValueError(f"Duplicate primary-key rows found for key {key}.")


def validate_prices(data: pd.DataFrame) -> ValidationResult:
    issues: list[ValidationIssue] = []
    required = {"security_id", "trade_date", "adjusted_close", "source"}
    missing = required.difference(data.columns)
    if missing:
        issues.append(_issue("prices", "required_fields", f"Missing required columns: {sorted(missing)}", len(data)))
        return _result(issues)
    duplicate_count = int(data.duplicated(subset=["security_id", "trade_date", "source"], keep=False).sum())
    if duplicate_count:
        issues.append(_issue("prices", "duplicate_natural_key", "Duplicate price natural keys detected.", duplicate_count))
    adjusted_close = pd.to_numeric(data["adjusted_close"], errors="coerce")
    invalid_price_count = int((adjusted_close.isna() | (adjusted_close <= 0)).sum())
    if invalid_price_count:
        issues.append(_issue("prices", "positive_adjusted_close", "Adjusted close must be positive.", invalid_price_count))
    if {"high_price", "low_price"}.issubset(data.columns):
        high = pd.to_numeric(data["high_price"], errors="coerce")
        low = pd.to_numeric(data["low_price"], errors="coerce")
        bad_hilo = int(((high < low) & high.notna() & low.notna()).sum())
        if bad_hilo:
            issues.append(_issue("prices", "high_greater_equal_low", "High price must be greater than or equal to low price.", bad_hilo))
    if "volume" in data:
        volume = pd.to_numeric(data["volume"], errors="coerce")
        bad_volume = int(((volume < 0) & volume.notna()).sum())
        if bad_volume:
            issues.append(_issue("prices", "non_negative_volume", "Volume must be non-negative.", bad_volume))
    if "trading_currency" in data:
        currency_mask = data["trading_currency"].dropna().astype(str).str.upper().isin(VALID_CURRENCIES)
        bad_currency = int((~currency_mask).sum())
        if bad_currency:
            issues.append(_issue("prices", "valid_currency", "Trading currency must be recognised.", bad_currency))
    trade_dates = pd.to_datetime(data["trade_date"], errors="coerce")
    future_count = int((trade_dates.isna() | (trade_dates > pd.Timestamp.today().normalize() + pd.Timedelta(days=1))).sum())
    if future_count:
        issues.append(_issue("prices", "no_future_trade_date", "Trade date is beyond configured tolerance.", future_count))
    return _result(issues)


def validate_fundamentals(data: pd.DataFrame) -> ValidationResult:
    issues: list[ValidationIssue] = []
    required = {"security_id", "fiscal_period_end", "available_from", "vintage_id", "source"}
    missing = required.difference(data.columns)
    if missing:
        issues.append(_issue("fundamentals", "required_fields", f"Missing required columns: {sorted(missing)}", len(data)))
    if "available_from" in data and "fiscal_period_end" in data:
        available = pd.to_datetime(data["available_from"], errors="coerce")
        fiscal_end = pd.to_datetime(data["fiscal_period_end"], errors="coerce")
        impossible = int((available.isna() | fiscal_end.isna() | (available < fiscal_end)).sum())
        if impossible:
            issues.append(_issue("fundamentals", "logical_available_from", "available_from cannot be before fiscal period end.", impossible))
    numeric_columns = [c for c in data.columns if c in {"revenue", "operating_income", "net_income", "free_cash_flow", "total_assets", "total_debt"}]
    for column in numeric_columns:
        invalid = int(pd.to_numeric(data[column], errors="coerce").isna().sum() - data[column].isna().sum())
        if invalid:
            issues.append(_issue("fundamentals", f"numeric_{column}", f"{column} must be numeric.", invalid))
    return _result(issues)


def validate_dividends(data: pd.DataFrame) -> ValidationResult:
    issues: list[ValidationIssue] = []
    required = {"security_id", "ex_dividend_date", "dividend_amount", "available_from", "source"}
    missing = required.difference(data.columns)
    if missing:
        issues.append(_issue("dividends", "required_fields", f"Missing required columns: {sorted(missing)}", len(data)))
    if "dividend_amount" in data:
        amount = pd.to_numeric(data["dividend_amount"], errors="coerce")
        invalid = int((amount.isna() | (amount < 0)).sum())
        if invalid:
            issues.append(_issue("dividends", "non_negative_amount", "Dividend amount must be non-negative.", invalid))
    return _result(issues)


def validate_fx_rates(data: pd.DataFrame) -> ValidationResult:
    issues: list[ValidationIssue] = []
    required = {"base_currency", "quote_currency", "rate_date", "rate", "source"}
    missing = required.difference(data.columns)
    if missing:
        issues.append(_issue("fx", "required_fields", f"Missing required columns: {sorted(missing)}", len(data)))
    if "rate" in data:
        rate = pd.to_numeric(data["rate"], errors="coerce")
        invalid = int((rate.isna() | (rate <= 0)).sum())
        if invalid:
            issues.append(_issue("fx", "positive_rate", "FX rate must be positive.", invalid))
    if {"base_currency", "quote_currency"}.issubset(data.columns):
        same = int(data["base_currency"].astype(str).str.upper().eq(data["quote_currency"].astype(str).str.upper()).sum())
        if same:
            issues.append(_issue("fx", "different_currency_pair", "Base and quote currency must differ.", same))
    return _result(issues)


def validate_macro_observations(data: pd.DataFrame) -> ValidationResult:
    issues: list[ValidationIssue] = []
    required = {"series_id", "observation_date", "vintage_date", "available_from", "source"}
    missing = required.difference(data.columns)
    if missing:
        issues.append(_issue("macro", "required_fields", f"Missing required columns: {sorted(missing)}", len(data)))
    duplicate_count = int(data.duplicated(subset=["series_id", "observation_date", "vintage_date", "source"], keep=False).sum()) if not missing else 0
    if duplicate_count:
        issues.append(_issue("macro", "preserve_revisions", "Duplicate macro vintage keys detected.", duplicate_count))
    return _result(issues)


def validate_news_documents(data: pd.DataFrame) -> ValidationResult:
    issues: list[ValidationIssue] = []
    required = {"document_id", "available_from", "retrieved_at", "payload_hash", "source"}
    missing = required.difference(data.columns)
    if missing:
        issues.append(_issue("news", "required_fields", f"Missing required columns: {sorted(missing)}", len(data)))
    return _result(issues)
