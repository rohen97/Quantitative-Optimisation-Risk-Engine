from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, linprog, milp

from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DuckDBRepository
from src.features.feature_store import build_feature_store
from src.features.risk_features import build_price_risk_features
from src.models.forecasting import build_ml_forecast_features
from src.models.scorecard import build_scorecard
from src.optimisation.optimiser_inputs import build_optimiser_input_dataset
from src.optimisation.optimisers import cvar_constrained_portfolio
from src.optimisation.constraints import build_retention_eligibility_mask
from src.utils.config import ROOT, load_yaml
from src.validation.transaction_cost_validation import estimate_transaction_cost
from src.validation.risk_models import (
    RiskModelSettings,
    forecast_risk,
    select_risk_model,
    serialise_scores,
)


LOGGER = logging.getLogger(__name__)
ARTIFACT_VERSION = 3
FORECAST_HORIZONS = (3, 6, 9, 12)
CASH_SECURITY_ID = 'CASH.USD'
MONETARY_COLUMNS = (
    'revenue',
    'operating_income',
    'net_income',
    'operating_cash_flow',
    'capital_expenditure',
    'free_cash_flow',
    'total_assets',
    'total_liabilities',
    'total_debt',
    'cash_and_equivalents',
    'shareholders_equity',
    'dividends_paid',
    'ebitda',
    'interest_expense',
)


@dataclass(frozen=True)
class WalkForwardConfig:
    output_directory: Path
    start_date: pd.Timestamp
    forecast_end_date: pd.Timestamp
    strategy_end_date: pd.Timestamp
    evidence_mode: str = 'reconstructed_pit_proxy'
    filing_lag_days: int = 120
    minimum_annual_periods: int = 2
    minimum_training_price_rows: int = 756
    price_lookback_rows: int = 756
    outcome_date_tolerance_days: int = 14
    portfolio_nav_usd: float = 100_000_000.0
    primary_strategy: str = 'wolf_cvar'
    approval_cap: str = 'CONDITIONALLY_APPROVED'
    maximum_rebalance_turnover: float = 0.10
    risk_ewma_decay: float = 0.94
    risk_lookback_rows: int = 252
    risk_candidate_models: tuple[str, ...] = ('ewma_normal',)
    risk_calibration_rows: int = 63
    risk_minimum_training_rows: int = 120
    risk_student_t_degrees_freedom: float = 7.0
    risk_dcc_alpha: float = 0.03
    risk_dcc_beta: float = 0.95
    risk_correlation_shrinkage: float = 0.10
    risk_calibration_scale_factors: tuple[float, ...] = (1.0,)
    risk_exception_response_multiplier: float = 1.10
    risk_exception_response_days: int = 1


@dataclass(frozen=True)
class WalkForwardResult:
    output_directory: Path
    forecast_rows: int
    outcome_rows: int
    portfolio_months: int
    risk_observations: int
    security_count: int
    evidence_mode: str


def load_walk_forward_config(
    output_directory: str | Path | None = None,
    **overrides: Any,
) -> WalkForwardConfig:
    raw = load_yaml('configs/validation.yaml').get('validation', {}).get('walk_forward', {})
    values = {**raw, **{key: value for key, value in overrides.items() if value is not None}}
    output = Path(output_directory or values.get('output_directory', 'reports/outputs/walk_forward'))
    if not output.is_absolute():
        output = ROOT / output
    risk_forecast = values.get('risk_forecast', {})
    risk_ewma_decay = float(risk_forecast.get('ewma_decay', 0.94))
    if not 0 < risk_ewma_decay < 1:
        raise ValueError('Walk-forward risk EWMA decay must be between zero and one.')
    candidate_models = tuple(
        risk_forecast.get(
            'candidate_models',
            [risk_forecast.get('model', 'ewma_normal')],
        )
    )
    maximum_rebalance_turnover = float(
        values.get('maximum_rebalance_turnover', 0.10)
    )
    if not 0 <= maximum_rebalance_turnover <= 1:
        raise ValueError('Walk-forward turnover limit must be between zero and one.')
    config = WalkForwardConfig(
        output_directory=output,
        start_date=pd.Timestamp(values.get('start_date', '2024-06-30')).normalize(),
        forecast_end_date=pd.Timestamp(values.get('forecast_end_date', '2025-07-31')).normalize(),
        strategy_end_date=pd.Timestamp(values.get('strategy_end_date', '2026-06-30')).normalize(),
        evidence_mode=str(values.get('evidence_mode', 'reconstructed_pit_proxy')),
        filing_lag_days=int(values.get('filing_lag_days', 120)),
        minimum_annual_periods=int(values.get('minimum_annual_periods', 2)),
        minimum_training_price_rows=int(values.get('minimum_training_price_rows', 756)),
        price_lookback_rows=int(values.get('price_lookback_rows', 756)),
        outcome_date_tolerance_days=int(values.get('outcome_date_tolerance_days', 14)),
        portfolio_nav_usd=float(values.get('portfolio_nav_usd', 100_000_000)),
        primary_strategy=str(values.get('primary_strategy', 'wolf_cvar')),
        approval_cap=str(values.get('approval_cap', 'CONDITIONALLY_APPROVED')),
        maximum_rebalance_turnover=maximum_rebalance_turnover,
        risk_ewma_decay=risk_ewma_decay,
        risk_lookback_rows=int(risk_forecast.get('lookback_rows', 252)),
        risk_candidate_models=candidate_models,
        risk_calibration_rows=int(risk_forecast.get('calibration_rows', 63)),
        risk_minimum_training_rows=int(
            risk_forecast.get('minimum_training_rows', 120)
        ),
        risk_student_t_degrees_freedom=float(
            risk_forecast.get('student_t_degrees_freedom', 7.0)
        ),
        risk_dcc_alpha=float(risk_forecast.get('dcc_alpha', 0.03)),
        risk_dcc_beta=float(risk_forecast.get('dcc_beta', 0.95)),
        risk_correlation_shrinkage=float(
            risk_forecast.get('correlation_shrinkage', 0.10)
        ),
        risk_calibration_scale_factors=tuple(
            float(value)
            for value in risk_forecast.get('calibration_scale_factors', [1.0])
        ),
        risk_exception_response_multiplier=float(
            risk_forecast.get('exception_response_multiplier', 1.10)
        ),
        risk_exception_response_days=int(
            risk_forecast.get('exception_response_days', 1)
        ),
    )
    if config.risk_exception_response_multiplier < 1.0:
        raise ValueError('Risk exception response multiplier cannot be below one.')
    if config.risk_exception_response_days < 0:
        raise ValueError('Risk exception response days cannot be negative.')
    _risk_model_settings(config).validate()
    return config


def _risk_model_settings(config: WalkForwardConfig) -> RiskModelSettings:
    return RiskModelSettings(
        ewma_decay=config.risk_ewma_decay,
        lookback_rows=config.risk_lookback_rows,
        candidate_models=config.risk_candidate_models,
        calibration_rows=config.risk_calibration_rows,
        minimum_training_rows=config.risk_minimum_training_rows,
        student_t_degrees_freedom=config.risk_student_t_degrees_freedom,
        dcc_alpha=config.risk_dcc_alpha,
        dcc_beta=config.risk_dcc_beta,
        correlation_shrinkage=config.risk_correlation_shrinkage,
        calibration_scale_factors=config.risk_calibration_scale_factors,
    )


def reconstruct_statement_availability(
    statements: pd.DataFrame,
    filing_lag_days: int,
) -> pd.DataFrame:
    result = statements.copy()
    period_end = pd.to_datetime(
        result['fiscal_period_end'], errors='coerce', utc=True
    ).dt.tz_localize(None)
    filing_date = pd.to_datetime(
        result.get('filing_date', pd.Series(pd.NaT, index=result.index)),
        errors='coerce',
        utc=True,
    ).dt.tz_localize(None)
    observed_acceptance = pd.to_datetime(
        result.get(
            'observed_acceptance_datetime',
            pd.Series(pd.NaT, index=result.index),
        ),
        errors='coerce',
        utc=True,
    ).dt.tz_localize(None)
    explicit_available = pd.to_datetime(
        result.get('available_from', pd.Series(pd.NaT, index=result.index)),
        errors='coerce',
        utc=True,
    ).dt.tz_localize(None)
    proxy_date = period_end + pd.to_timedelta(int(filing_lag_days), unit='D')
    source = result.get('source', pd.Series('', index=result.index)).astype(str)
    trusted_database_snapshot = source.str.contains(
        'bloomberg_database_as_of',
        case=False,
        na=False,
    )
    valid_database_snapshot = (
        trusted_database_snapshot
        & explicit_available.notna()
        & period_end.notna()
        & explicit_available.ge(period_end)
    )
    trusted_filing_source = ~source.str.contains(
        'yahoo_finance_timeseries',
        case=False,
        na=False,
    )
    valid_filing = (
        filing_date.notna()
        & period_end.notna()
        & filing_date.ge(period_end)
        & trusted_filing_source
    )
    valid_acceptance = (
        observed_acceptance.notna()
        & period_end.notna()
        & observed_acceptance.ge(period_end)
    )
    result['reconstructed_available_from'] = explicit_available.where(
        valid_database_snapshot,
        observed_acceptance.where(
            valid_acceptance,
            filing_date.where(valid_filing, proxy_date),
        ),
    )
    result['availability_basis'] = np.select(
        [valid_database_snapshot, valid_acceptance, valid_filing],
        [
            'bloomberg_fundamental_database_as_of',
            'observed_sec_acceptance_datetime',
            'reported_filing_date',
        ],
        default=f'fiscal_period_end_plus_{int(filing_lag_days)}d',
    )
    return result


def _normalise_fx_currency(values: pd.Series) -> pd.Series:
    aliases = {'GBX': 'GBP', 'GBP': 'GBP', 'GBp': 'GBP'}
    clean = values.fillna('USD').astype(str).str.strip()
    return clean.map(lambda value: aliases.get(value, value.upper()))


class _FxMatcher:
    def __init__(self, rates: pd.DataFrame) -> None:
        self._rates: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        clean = rates.copy()
        clean['rate_date'] = pd.to_datetime(clean['rate_date'])
        clean['quote_currency'] = _normalise_fx_currency(clean['quote_currency'])
        clean['rate'] = pd.to_numeric(clean['rate'], errors='coerce')
        clean = clean.loc[clean['rate'].gt(0)].sort_values(['quote_currency', 'rate_date'])
        for currency, group in clean.groupby('quote_currency', sort=False):
            self._rates[str(currency)] = (
                group['rate_date'].to_numpy(dtype='datetime64[ns]'),
                group['rate'].to_numpy(dtype=float),
            )

    def match(self, currencies: pd.Series, dates: pd.Series) -> pd.Series:
        original_index = currencies.index
        normalised = _normalise_fx_currency(currencies).reset_index(drop=True)
        query_dates = pd.to_datetime(dates).reset_index(drop=True).to_numpy(
            dtype='datetime64[ns]'
        )
        output = np.full(len(normalised), np.nan, dtype=float)
        for currency, positions in normalised.groupby(normalised, sort=False).groups.items():
            indexes = np.asarray(list(positions), dtype=int)
            if currency == 'USD':
                output[indexes] = 1.0
                continue
            values = self._rates.get(str(currency))
            if values is None:
                continue
            rate_dates, rates = values
            matched = np.searchsorted(rate_dates, query_dates[indexes], side='right') - 1
            valid = matched >= 0
            output[indexes[valid]] = rates[matched[valid]]
        return pd.Series(output, index=original_index, dtype=float)


class _MarketCapMatcher:
    def __init__(self, snapshots: pd.DataFrame) -> None:
        self._groups: dict[str, pd.DataFrame] = {}
        if snapshots.empty:
            return
        clean = snapshots.copy()
        clean['available_from'] = pd.to_datetime(clean['available_from'])
        clean['as_of_date'] = pd.to_datetime(clean['as_of_date'])
        clean = clean.sort_values(
            ['security_id', 'available_from', 'as_of_date', 'retrieved_at']
        )
        for security_id, group in clean.groupby('security_id', sort=False):
            self._groups[str(security_id)] = group.reset_index(drop=True)

    def match(self, security_ids: pd.Series, as_of_date: pd.Timestamp) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        target = np.datetime64(pd.Timestamp(as_of_date), 'ns')
        for security_id in map(str, security_ids):
            group = self._groups.get(security_id)
            if group is None:
                continue
            dates = group['available_from'].to_numpy(dtype='datetime64[ns]')
            position = int(np.searchsorted(dates, target, side='right')) - 1
            if position < 0:
                continue
            row = group.iloc[position]
            rows.append(
                {
                    'security_id': security_id,
                    'pit_market_cap_local': row.get('market_cap_local'),
                    'pit_shares_outstanding': row.get('shares_outstanding'),
                    'pit_market_cap_currency': row.get('currency'),
                    'pit_market_cap_as_of_date': row.get('as_of_date'),
                    'pit_market_cap_available_from': row.get('available_from'),
                }
            )
        return pd.DataFrame(rows)


class _PriceMatcher:
    def __init__(self, prices: pd.DataFrame) -> None:
        self.prices = prices.sort_values(['security_id', 'trade_date']).reset_index(drop=True)
        self._groups: dict[str, pd.DataFrame] = {
            str(security_id): group.reset_index(drop=True)
            for security_id, group in self.prices.groupby('security_id', sort=False)
        }

    def trailing(
        self,
        security_ids: pd.Series | list[str],
        as_of_date: pd.Timestamp,
        rows: int,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        history: list[pd.DataFrame] = []
        latest: list[dict[str, Any]] = []
        target = np.datetime64(pd.Timestamp(as_of_date), 'ns')
        for security_id in map(str, security_ids):
            group = self._groups.get(security_id)
            if group is None:
                continue
            dates = group['trade_date'].to_numpy(dtype='datetime64[ns]')
            end = int(np.searchsorted(dates, target, side='right'))
            if end <= 0:
                continue
            start = max(0, end - int(rows))
            history.append(group.iloc[start:end])
            row = group.iloc[end - 1].to_dict()
            row['history_row_count'] = end
            latest.append(row)
        recent = pd.concat(history, ignore_index=True) if history else pd.DataFrame()
        return recent, pd.DataFrame(latest)

    def match_requests(
        self,
        requests: pd.DataFrame,
        date_column: str,
        direction: str,
        tolerance_days: int | None = None,
    ) -> pd.DataFrame:
        if requests.empty:
            return requests.copy()
        requests = requests.reset_index(drop=True)
        rows: list[dict[str, Any]] = []
        for security_id, group_requests in requests.groupby('security_id', sort=False):
            prices = self._groups.get(str(security_id))
            if prices is None:
                continue
            price_dates = prices['trade_date'].to_numpy(dtype='datetime64[ns]')
            query_dates = pd.to_datetime(group_requests[date_column]).to_numpy(
                dtype='datetime64[ns]'
            )
            positions = np.searchsorted(
                price_dates,
                query_dates,
                side='right' if direction == 'backward' else 'left',
            )
            if direction == 'backward':
                positions -= 1
            valid = (positions >= 0) & (positions < len(prices))
            for request_position, price_position, is_valid in zip(
                group_requests.index,
                positions,
                valid,
            ):
                if not is_valid:
                    continue
                request = requests.loc[request_position].to_dict()
                price = prices.iloc[int(price_position)]
                matched_date = pd.Timestamp(price['trade_date'])
                requested_date = pd.Timestamp(request[date_column])
                gap = abs((matched_date - requested_date).days)
                if tolerance_days is not None and gap > tolerance_days:
                    continue
                request.update(
                    {
                        'matched_trade_date': matched_date,
                        'matched_adjusted_close': float(price['adjusted_close']),
                        'matched_close_price': float(price['close_price']),
                    }
                )
                rows.append(request)
        return pd.DataFrame(rows)

    def between(
        self,
        security_ids: list[str],
        start_exclusive: pd.Timestamp,
        end_inclusive: pd.Timestamp,
    ) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        start = np.datetime64(pd.Timestamp(start_exclusive), 'ns')
        end = np.datetime64(pd.Timestamp(end_inclusive), 'ns')
        for security_id in map(str, security_ids):
            group = self._groups.get(security_id)
            if group is None:
                continue
            dates = group['trade_date'].to_numpy(dtype='datetime64[ns]')
            left = int(np.searchsorted(dates, start, side='right'))
            right = int(np.searchsorted(dates, end, side='right'))
            if right > left:
                frames.append(group.iloc[left:right])
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _load_source_data(
    repository: DuckDBRepository,
    config: WalkForwardConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    minimum_periods = int(config.minimum_annual_periods)
    universe = repository.query(
        f'''
        WITH coverage AS (
            SELECT security_id, COUNT(DISTINCT fiscal_period_end) AS annual_periods
            FROM fundamentals_reported
            WHERE fiscal_period_type = 'annual'
              AND LOWER(source) NOT LIKE '%mock%'
              AND LOWER(source) NOT LIKE '%synthetic%'
            GROUP BY security_id
            HAVING COUNT(DISTINCT fiscal_period_end) >= {minimum_periods}
        ),
        reference AS (
            SELECT * EXCLUDE (reference_row)
            FROM (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY security_id ORDER BY as_of_date DESC, retrieved_at DESC
                ) AS reference_row
                FROM security_reference_snapshots
            )
            WHERE reference_row = 1
        )
        SELECT
            s.security_id, s.security_id AS ticker,
            'NAME:' || REGEXP_REPLACE(LOWER(s.company_name), '[^a-z0-9]+', '', 'g') AS issuer_id,
            s.company_name, s.instrument_type, s.listing_status, s.exchange_code,
            s.country, s.region,
            COALESCE(NULLIF(r.sector, ''), NULLIF(s.sector, ''), 'Unknown') AS sector,
            COALESCE(NULLIF(r.industry, ''), NULLIF(s.industry, ''), 'Unknown') AS industry,
            COALESCE(NULLIF(r.quote_currency, ''), NULLIF(s.trading_currency, ''), 'USD') AS currency,
            COALESCE(NULLIF(r.financial_currency, ''), NULLIF(s.domicile_currency, ''), 'USD') AS financial_currency,
            COALESCE(r.price_scale, 1.0) AS price_scale,
            r.shares_outstanding AS reference_shares_outstanding,
            r.average_daily_value_usd AS reference_average_daily_value_usd,
            c.annual_periods
        FROM securities s
        JOIN coverage c USING (security_id)
        LEFT JOIN reference r USING (security_id)
        WHERE s.listing_status = 'Active'
          AND s.instrument_type = 'Equity'
          AND s.region IN ('US', 'UK', 'DACH', 'Mainland China', 'Hong Kong', 'EU ex-DACH')
        ORDER BY s.region, s.security_id
        '''
    )
    security_ids = universe['security_id'].astype(str).tolist()
    placeholder = chr(63)
    statements = repository.query(
        f'''
        WITH ranked AS (
            SELECT *,
                CASE
                    WHEN source = 'bloomberg_database_as_of' THEN 1
                    WHEN source = 'sec_companyfacts' THEN 2
                    WHEN source IN (
                        'finnhub_reported',
                        'eastmoney_china_financials',
                        'eastmoney_hk_financials'
                    ) THEN 3
                    WHEN source LIKE 'akshare%' THEN 4
                    WHEN source = 'yahoo_finance_timeseries' THEN 5
                    ELSE 6
                END AS source_priority
            FROM fundamentals_reported
            WHERE security_id IN (SELECT UNNEST({placeholder}))
              AND fiscal_period_type = 'annual'
              AND LOWER(source) NOT LIKE '%mock%'
              AND LOWER(source) NOT LIKE '%synthetic%'
        ), selected AS (
            SELECT * EXCLUDE (source_priority)
            FROM ranked
            QUALIFY source_priority = MIN(source_priority) OVER (
                PARTITION BY security_id, fiscal_period_end, fiscal_period_type
            )
        ), observed_filings AS (
            SELECT
                security_id,
                report_date,
                MIN(acceptance_datetime) AS observed_acceptance_datetime,
                ARG_MIN(source, acceptance_datetime) AS filing_metadata_source
            FROM filing_metadata
            WHERE acceptance_datetime IS NOT NULL
            GROUP BY security_id, report_date
        )
        SELECT
            selected.*,
            observed_filings.observed_acceptance_datetime,
            observed_filings.filing_metadata_source
        FROM selected
        LEFT JOIN observed_filings
          ON selected.security_id = observed_filings.security_id
         AND selected.fiscal_period_end = observed_filings.report_date
        ORDER BY security_id, fiscal_period_end
        ''',
        [security_ids],
    )
    price_end = max(
        config.strategy_end_date + pd.DateOffset(months=2),
        config.forecast_end_date + pd.DateOffset(months=13),
    ).date()
    prices = repository.query(
        f'''
        SELECT
            security_id, trade_date, close_price,
            COALESCE(adjusted_close, close_price) AS adjusted_close,
            volume, trading_currency, source
        FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY security_id, trade_date
                ORDER BY
                    CASE WHEN adjusted_close IS NOT NULL THEN 0 ELSE 1 END,
                    CASE
                        WHEN source = 'yfinance' THEN 1
                        WHEN source = 'eodhd' THEN 2
                        WHEN source = 'alpaca' THEN 3
                        WHEN source = 'tickdb' THEN 4
                        ELSE 5
                    END,
                    retrieved_at DESC
            ) AS source_row
            FROM prices_daily
            WHERE security_id IN (SELECT UNNEST({placeholder}))
              AND trade_date <= {placeholder}
              AND COALESCE(adjusted_close, close_price) > 0
        )
        WHERE source_row = 1
        ORDER BY security_id, trade_date
        ''',
        [security_ids, price_end],
    )
    fx = repository.query(
        '''
        SELECT rate_date, quote_currency, rate
        FROM fx_rates
        WHERE base_currency = 'USD' AND rate > 0
        ORDER BY quote_currency, rate_date
        '''
    )
    market_caps = repository.query(
        f'''
        SELECT
            security_id, as_of_date, available_from, market_cap_local,
            shares_outstanding, currency, retrieved_at, vintage_id
        FROM market_cap_vintages
        WHERE security_id IN (SELECT UNNEST({placeholder}))
          AND available_from <= {placeholder}
        ORDER BY security_id, available_from, as_of_date
        ''',
        [security_ids, config.strategy_end_date],
    )
    return universe, statements, prices, fx, market_caps


def _prepare_prices(prices: pd.DataFrame) -> pd.DataFrame:
    result = prices.copy()
    result['trade_date'] = pd.to_datetime(result['trade_date'])
    for column in ('close_price', 'adjusted_close', 'volume'):
        result[column] = pd.to_numeric(result[column], errors='coerce')
    result = result.dropna(
        subset=['security_id', 'trade_date', 'close_price', 'adjusted_close']
    )
    grouped = result.groupby('security_id', sort=False)
    result['raw_return'] = grouped['adjusted_close'].pct_change(fill_method=None)
    result['return_outlier_flag'] = result['raw_return'].abs().gt(1.0)
    result['return'] = result['raw_return'].clip(-1.0, 1.0).fillna(0.0)
    result['ticker'] = result['security_id'].astype(str)
    return result


def _prepare_statements(
    statements: pd.DataFrame,
    universe: pd.DataFrame,
    fx_matcher: _FxMatcher,
    filing_lag_days: int,
) -> pd.DataFrame:
    result = reconstruct_statement_availability(statements, filing_lag_days)
    result['fiscal_period_end'] = pd.to_datetime(result['fiscal_period_end'])
    result = result.merge(
        universe[['security_id', 'financial_currency']],
        on='security_id',
        how='left',
    )
    statement_currency = result['currency'].where(
        result['currency'].fillna('').astype(str).str.strip().ne(''),
        result['financial_currency'],
    )
    result['_units_per_usd'] = fx_matcher.match(
        statement_currency,
        result['fiscal_period_end'],
    )
    for column in MONETARY_COLUMNS:
        result[f'{column}_usd'] = (
            pd.to_numeric(result[column], errors='coerce') / result['_units_per_usd']
        )
    result['diluted_shares'] = pd.to_numeric(result['diluted_shares'], errors='coerce')
    result['dps'] = (
        result['dividends_paid_usd'].abs()
        / result['diluted_shares'].replace(0, np.nan)
    )
    return result.sort_values(['security_id', 'fiscal_period_end']).reset_index(drop=True)


def _annualised_dps_growth(history: pd.DataFrame, periods: int) -> pd.Series:
    valid = (
        history.loc[history['dps'].gt(0)]
        .groupby('security_id', group_keys=False)
        .tail(periods)
    )
    if valid.empty:
        return pd.Series(dtype=float)
    summary = valid.groupby('security_id').agg(
        first_value=('dps', 'first'),
        last_value=('dps', 'last'),
        first_date=('fiscal_period_end', 'first'),
        last_date=('fiscal_period_end', 'last'),
        observations=('dps', 'size'),
    )
    years = (
        pd.to_datetime(summary['last_date']) - pd.to_datetime(summary['first_date'])
    ).dt.days.div(365.25).clip(lower=1.0)
    growth = np.power(summary['last_value'] / summary['first_value'], 1.0 / years) - 1.0
    return growth.where(summary['observations'].ge(2))


def _fundamental_snapshot(
    statements: pd.DataFrame,
    as_of_date: pd.Timestamp,
    minimum_periods: int,
) -> pd.DataFrame:
    available = statements.loc[
        pd.to_datetime(statements['reconstructed_available_from']).le(as_of_date)
    ].copy()
    if available.empty:
        return pd.DataFrame()
    available = available.sort_values(
        [
            'security_id',
            'fiscal_period_end',
            'reconstructed_available_from',
            'retrieved_at',
        ]
    )
    available = available.groupby(
        ['security_id', 'fiscal_period_end', 'fiscal_period_type'],
        as_index=False,
        sort=False,
    ).tail(1)
    available = available.sort_values(['security_id', 'fiscal_period_end'])
    available['_period_count'] = available.groupby('security_id')[
        'security_id'
    ].transform('size')
    available = available.loc[available['_period_count'].ge(minimum_periods)]
    if available.empty:
        return pd.DataFrame()
    grouped = available.groupby('security_id', sort=False)
    available['_previous_revenue_usd'] = grouped['revenue_usd'].shift(1)
    available['_dps_change'] = grouped['dps'].pct_change(fill_method=None)
    latest = grouped.tail(1).set_index('security_id')
    trailing_five = grouped.tail(5)
    stability = trailing_five.groupby('security_id').agg(
        positive_fcf_years_5=(
            'free_cash_flow_usd',
            lambda values: int(values.gt(0).sum()),
        ),
        fcf_mean_abs=(
            'free_cash_flow_usd',
            lambda values: float(values.abs().mean()),
        ),
        fcf_std=(
            'free_cash_flow_usd',
            lambda values: float(values.std(ddof=0)),
        ),
        fundamentals_period_count=('fiscal_period_end', 'size'),
    )
    stability['fcf_stability'] = (
        100.0
        * (
            1.0
            - (stability['fcf_std'] / stability['fcf_mean_abs'])
            .div(1.5)
            .clip(0, 1)
        )
    ).where(stability['fcf_mean_abs'].gt(0))
    dividend_cut = (
        grouped.tail(4)
        .groupby('security_id')['_dps_change']
        .apply(lambda values: float(values.lt(-0.20).any()))
        .rename('dividend_cut_flag_3y')
    )
    result = latest.join(stability).join(dividend_cut)
    result['dividend_growth_3y'] = _annualised_dps_growth(available, 4)
    result['dividend_growth_5y'] = _annualised_dps_growth(available, 6)
    return result.reset_index()


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    values = pd.to_numeric(numerator, errors='coerce') / pd.to_numeric(
        denominator,
        errors='coerce',
    ).replace(0, np.nan)
    return values.replace([np.inf, -np.inf], np.nan)


def _build_anchor_inputs(
    universe: pd.DataFrame,
    statements: pd.DataFrame,
    price_matcher: _PriceMatcher,
    fx_matcher: _FxMatcher,
    market_cap_matcher: _MarketCapMatcher,
    as_of_date: pd.Timestamp,
    config: WalkForwardConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    financials = _fundamental_snapshot(
        statements,
        as_of_date,
        config.minimum_annual_periods,
    )
    if financials.empty:
        return pd.DataFrame(), pd.DataFrame()
    financials = financials.drop(
        columns=['currency', 'financial_currency', 'ticker'],
        errors='ignore',
    )
    candidates = universe.merge(financials, on='security_id', how='inner')
    recent, latest_prices = price_matcher.trailing(
        candidates['security_id'],
        as_of_date,
        config.price_lookback_rows,
    )
    if recent.empty or latest_prices.empty:
        return pd.DataFrame(), pd.DataFrame()
    latest = latest_prices[
        [
            'security_id',
            'trade_date',
            'close_price',
            'adjusted_close',
            'history_row_count',
        ]
    ].rename(
        columns={
            'trade_date': 'latest_trade_date',
            'close_price': 'anchor_close_price',
            'adjusted_close': 'anchor_adjusted_close',
        }
    )
    candidates = candidates.merge(latest, on='security_id', how='inner')
    candidates = candidates.loc[
        candidates['history_row_count'].ge(config.minimum_training_price_rows)
    ].copy()
    freshness = as_of_date - pd.to_datetime(candidates['latest_trade_date'])
    candidates = candidates.loc[
        freshness.dt.days.le(config.outcome_date_tolerance_days)
    ].copy()
    if candidates.empty:
        return pd.DataFrame(), pd.DataFrame()

    candidates['_quote_fx'] = fx_matcher.match(
        candidates['currency'],
        pd.Series(as_of_date, index=candidates.index),
    )
    candidates['price_scale'] = pd.to_numeric(
        candidates['price_scale'],
        errors='coerce',
    ).fillna(1.0)
    matched_market_caps = market_cap_matcher.match(
        candidates['security_id'],
        as_of_date,
    )
    if not matched_market_caps.empty:
        candidates = candidates.merge(
            matched_market_caps,
            on='security_id',
            how='left',
        )
    else:
        for column in (
            'pit_market_cap_local',
            'pit_shares_outstanding',
            'pit_market_cap_currency',
            'pit_market_cap_as_of_date',
            'pit_market_cap_available_from',
        ):
            candidates[column] = np.nan
    valuation_shares = pd.to_numeric(
        candidates['pit_shares_outstanding'],
        errors='coerce',
    ).fillna(pd.to_numeric(candidates['diluted_shares'], errors='coerce'))
    price_implied_market_cap = (
        candidates['anchor_close_price']
        * candidates['price_scale']
        * valuation_shares
        / candidates['_quote_fx']
    )
    market_cap_currency = candidates['pit_market_cap_currency'].where(
        candidates['pit_market_cap_currency'].fillna('').astype(str).str.strip().ne(''),
        candidates['currency'],
    )
    market_cap_fx = fx_matcher.match(
        market_cap_currency,
        pd.Series(as_of_date, index=candidates.index),
    )
    pit_market_cap_usd = (
        pd.to_numeric(candidates['pit_market_cap_local'], errors='coerce')
        / market_cap_fx
    )
    candidates['market_cap_usd'] = pit_market_cap_usd.where(
        pit_market_cap_usd.gt(0),
        price_implied_market_cap,
    )
    candidates['market_cap_data_source'] = np.where(
        pit_market_cap_usd.gt(0),
        'bloomberg_point_in_time',
        'price_times_available_shares',
    )
    candidates['revenue'] = pd.to_numeric(candidates['revenue_usd'], errors='coerce')
    candidates['operating_income'] = pd.to_numeric(
        candidates['operating_income_usd'],
        errors='coerce',
    )
    candidates['net_income'] = pd.to_numeric(
        candidates['net_income_usd'],
        errors='coerce',
    )
    candidates['operating_cash_flow'] = pd.to_numeric(
        candidates['operating_cash_flow_usd'],
        errors='coerce',
    )
    candidates['capex'] = pd.to_numeric(
        candidates['capital_expenditure_usd'],
        errors='coerce',
    ).abs()
    candidates['free_cash_flow'] = pd.to_numeric(
        candidates['free_cash_flow_usd'],
        errors='coerce',
    ).fillna(candidates['operating_cash_flow'] - candidates['capex'])
    candidates['total_debt'] = pd.to_numeric(
        candidates['total_debt_usd'],
        errors='coerce',
    )
    candidates['cash'] = pd.to_numeric(
        candidates['cash_and_equivalents_usd'],
        errors='coerce',
    )
    candidates['shareholders_equity'] = pd.to_numeric(
        candidates['shareholders_equity_usd'],
        errors='coerce',
    )
    candidates['ebitda'] = pd.to_numeric(
        candidates['ebitda_usd'],
        errors='coerce',
    ).fillna(candidates['operating_income'])
    candidates['interest_expense'] = pd.to_numeric(
        candidates['interest_expense_usd'],
        errors='coerce',
    ).abs()
    candidates['enterprise_value'] = (
        candidates['market_cap_usd'] + candidates['total_debt'] - candidates['cash']
    )
    candidates['dividends_paid'] = pd.to_numeric(
        candidates['dividends_paid_usd'],
        errors='coerce',
    ).abs()
    candidates['dividend_yield'] = _safe_ratio(
        candidates['dividends_paid'],
        candidates['market_cap_usd'],
    ).clip(0, 0.25)
    candidates['payout_ratio'] = _safe_ratio(
        candidates['dividends_paid'],
        candidates['net_income'],
    ).where(candidates['net_income'].gt(0))
    candidates['revenue_growth'] = _safe_ratio(
        candidates['revenue'],
        candidates['_previous_revenue_usd'],
    ) - 1.0
    candidates['ebitda_margin'] = _safe_ratio(
        candidates['ebitda'],
        candidates['revenue'],
    )
    candidates['net_income_margin'] = _safe_ratio(
        candidates['net_income'],
        candidates['revenue'],
    )
    candidates['free_cash_flow_yield'] = _safe_ratio(
        candidates['free_cash_flow'],
        candidates['market_cap_usd'],
    )
    candidates['fcf_margin'] = _safe_ratio(
        candidates['free_cash_flow'],
        candidates['revenue'],
    )
    candidates['cfo_to_net_income'] = _safe_ratio(
        candidates['operating_cash_flow'],
        candidates['net_income'],
    )

    candidates['_quote_fx'] = fx_matcher.match(
        candidates['currency'],
        pd.Series(as_of_date, index=candidates.index),
    )
    candidates['price_scale'] = pd.to_numeric(
        candidates['price_scale'],
        errors='coerce',
    ).fillna(1.0)
    candidates['market_cap_usd'] = (
        candidates['anchor_close_price']
        * candidates['price_scale']
        * pd.to_numeric(candidates['diluted_shares'], errors='coerce')
        / candidates['_quote_fx']
    )
    recent = recent.loc[
        recent['security_id'].astype(str).isin(candidates['security_id'].astype(str))
    ].copy()
    scales = candidates.set_index('security_id')['price_scale']
    recent['_price_scale'] = recent['security_id'].map(scales).fillna(1.0)
    recent['_traded_value_local'] = (
        recent['close_price'] * recent['volume'] * recent['_price_scale']
    )
    liquidity = (
        recent.groupby('security_id', group_keys=False)
        .tail(60)
        .groupby('security_id')
        .agg(
            avg_daily_traded_value_local=('_traded_value_local', 'mean'),
            liquidity_observation_count=(
                '_traded_value_local',
                lambda values: int(values.gt(0).sum()),
            ),
        )
    )
    candidates = candidates.join(liquidity, on='security_id')
    candidates['avg_daily_traded_value_usd'] = (
        candidates['avg_daily_traded_value_local'] / candidates['_quote_fx']
    )
    candidates['avg_daily_traded_value_usd'] = candidates[
        'avg_daily_traded_value_usd'
    ].where(
        candidates['avg_daily_traded_value_usd'].gt(0),
        pd.to_numeric(
            candidates['reference_average_daily_value_usd'],
            errors='coerce',
        ),
    )
    candidates['liquidity_observation_count'] = candidates[
        'liquidity_observation_count'
    ].where(
        candidates['liquidity_observation_count'].gt(0),
        np.where(candidates['avg_daily_traded_value_usd'].gt(0), 60, 0),
    )
    candidates = candidates.loc[
        candidates['market_cap_usd'].gt(0)
        & candidates['avg_daily_traded_value_usd'].gt(0)
        & pd.to_numeric(candidates['diluted_shares'], errors='coerce').gt(0)
    ].copy()
    if candidates.empty:
        return pd.DataFrame(), pd.DataFrame()

    candidates['net_debt_to_ebitda'] = _safe_ratio(
        candidates['total_debt'] - candidates['cash'],
        candidates['ebitda'],
    )
    candidates['interest_coverage'] = _safe_ratio(
        candidates['operating_income'],
        candidates['interest_expense'],
    )
    candidates['roe'] = _safe_ratio(
        candidates['net_income'],
        candidates['shareholders_equity'],
    )
    candidates['roic'] = _safe_ratio(
        candidates['operating_income'] * 0.79,
        candidates['total_debt'] + candidates['shareholders_equity'] - candidates['cash'],
    )
    candidates['pe_ratio'] = _safe_ratio(
        candidates['market_cap_usd'],
        candidates['net_income'],
    ).where(candidates['net_income'].gt(0))
    candidates['pb_ratio'] = _safe_ratio(
        candidates['market_cap_usd'],
        candidates['shareholders_equity'],
    ).where(candidates['shareholders_equity'].gt(0))
    candidates['ev_ebitda'] = _safe_ratio(
        candidates['enterprise_value'],
        candidates['ebitda'],
    ).where(candidates['ebitda'].gt(0))
    candidates['trailing_12m_dps'] = pd.to_numeric(
        candidates['dps'],
        errors='coerce',
    )
    candidates['fundamentals_as_of_date'] = pd.to_datetime(
        candidates['fiscal_period_end']
    )
    candidates['fundamentals_available_from'] = pd.to_datetime(
        candidates['reconstructed_available_from']
    )
    candidates['fundamentals_availability_basis'] = candidates[
        'availability_basis'
    ].astype(str)
    candidates['fundamentals_data_source'] = (
        candidates['source'].astype(str)
        + ':'
        + candidates['fundamentals_availability_basis']
    )
    coverage_columns = [
        'revenue',
        'operating_income',
        'net_income',
        'operating_cash_flow',
        'free_cash_flow',
        'total_debt',
        'cash',
        'shareholders_equity',
        'ebitda',
        'market_cap_usd',
        'dividend_yield',
        'payout_ratio',
    ]
    candidates['fundamentals_observation_count'] = candidates[
        coverage_columns
    ].notna().sum(axis=1)
    candidates['fundamentals_coverage_ratio'] = (
        candidates['fundamentals_observation_count'] / len(coverage_columns)
    )
    candidates['is_synthetic_fundamentals'] = False
    for column in ('cet1_ratio', 'solvency_ratio', 'npl_ratio', 'book_value_growth'):
        candidates[column] = np.nan

    universe_columns = [
        'security_id',
        'ticker',
        'issuer_id',
        'company_name',
        'instrument_type',
        'listing_status',
        'exchange_code',
        'country',
        'region',
        'sector',
        'industry',
        'currency',
        'avg_daily_traded_value_usd',
        'market_cap_usd',
        'liquidity_observation_count',
        'latest_trade_date',
    ]
    universe_snapshot = candidates[universe_columns].copy()
    universe_snapshot['liquidity_data_source'] = np.where(
        candidates['avg_daily_traded_value_local'].gt(0),
        'historical_price_volume_fx',
        'current_reference_adv_proxy',
    )
    universe_snapshot['market_cap_data_source'] = candidates[
        'market_cap_data_source'
    ].to_numpy()
    universe_snapshot['sector_data_source'] = 'current_security_reference_proxy'
    universe_snapshot['is_synthetic_data'] = False

    fundamental_columns = [
        'security_id',
        'ticker',
        'sector',
        'revenue',
        'revenue_growth',
        'ebitda',
        'ebitda_margin',
        'net_income',
        'net_income_margin',
        'operating_cash_flow',
        'capex',
        'free_cash_flow',
        'total_debt',
        'cash',
        'shareholders_equity',
        'enterprise_value',
        'dividend_yield',
        'trailing_12m_dps',
        'dividend_growth_3y',
        'dividend_growth_5y',
        'payout_ratio',
        'positive_fcf_years_5',
        'free_cash_flow_yield',
        'fcf_margin',
        'fcf_stability',
        'cfo_to_net_income',
        'net_debt_to_ebitda',
        'interest_coverage',
        'roe',
        'roic',
        'pe_ratio',
        'pb_ratio',
        'ev_ebitda',
        'dividend_cut_flag_3y',
        'cet1_ratio',
        'solvency_ratio',
        'npl_ratio',
        'book_value_growth',
        'fundamentals_data_source',
        'fundamentals_as_of_date',
        'fundamentals_available_from',
        'fundamentals_availability_basis',
        'fundamentals_period_count',
        'fundamentals_observation_count',
        'fundamentals_coverage_ratio',
        'is_synthetic_fundamentals',
    ]
    fundamentals = candidates[fundamental_columns].copy()

    active_ids = set(candidates['security_id'].astype(str))
    recent = recent.loc[recent['security_id'].astype(str).isin(active_ids)].copy()
    recent['date'] = pd.to_datetime(recent['trade_date'])
    recent['close'] = recent['adjusted_close']
    recent['full_history_daily_return'] = recent.groupby('ticker')['return'].transform(
        'mean'
    )
    risk_features = build_price_risk_features(recent)

    neutral = candidates[['security_id', 'ticker']].copy()
    neutral['sentiment_alt_data_score'] = 50.0
    neutral['news_sentiment_30d'] = 0.0
    neutral['negative_news_intensity'] = 0.0
    neutral['controversy_score'] = 0.0
    neutral['credit_stress_score'] = 0.0
    neutral['regulatory_risk_score'] = 0.0
    neutral['alt_data_review_required_flag'] = False
    neutral['alt_data_exclusion_flag'] = False
    regime = candidates[['ticker']].copy()
    regime['regime_suitability_score'] = 50.0
    regime['regime_risk_score'] = 50.0
    regime['regime_deterioration_probability'] = 0.0
    regime['regime_weight_adjustment'] = 0.0
    regime['regime_review_required_flag'] = False
    regime['regime_exclusion_flag'] = False
    regime['dominant_regime'] = 'historical_neutral'
    portfolio = pd.DataFrame(
        columns=[
            'ticker',
            'sector',
            'country',
            'region',
            'currency',
            'weight',
            'market_value_usd',
        ]
    )
    features = build_feature_store(
        universe_snapshot,
        recent,
        fundamentals,
        neutral,
        portfolio,
        regime,
        price_risk_features=risk_features,
    )
    features['as_of_date'] = pd.Timestamp(as_of_date)
    features['feature_month'] = pd.Timestamp(as_of_date).replace(day=1)
    features['available_from'] = pd.to_datetime(
        features['fundamentals_available_from']
    )
    features['price_feature_end_date'] = pd.to_datetime(features['latest_trade_date'])
    features['evidence_mode'] = config.evidence_mode
    features['historical_non_market_features_mode'] = 'neutral_no_historical_vintage'
    features['dividend_risk_score'] = 0.0
    features['dividend_risk_similarity_score'] = 50.0
    features['risk_reframing_score'] = 50.0
    features['distress_similarity_score'] = 50.0
    features['credit_stress_similarity_score'] = 50.0
    features['regulatory_risk_similarity_score'] = 50.0
    features['narrative_reframing_score'] = 50.0
    features['reframing_review_required_flag'] = False
    features['reframing_exclusion_flag'] = False
    features['markov_negative_to_distress_prob'] = 0.0
    features['governance_red_flag_count'] = 0
    return features.reset_index(drop=True), recent.reset_index(drop=True)


def _forecast_anchor(
    features: pd.DataFrame,
    as_of_date: pd.Timestamp,
    evidence_mode: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    outputs = build_ml_forecast_features(features)
    metadata_columns = [
        'ticker',
        'issuer_id',
        'country',
        'region',
        'sector',
        'currency',
        'fundamentals_as_of_date',
        'fundamentals_available_from',
        'fundamentals_availability_basis',
        'price_feature_end_date',
        'fundamentals_period_count',
    ]
    metadata = features[
        [column for column in metadata_columns if column in features]
    ].drop_duplicates('ticker')
    rows: list[pd.DataFrame] = []
    for months in FORECAST_HORIZONS:
        frame = outputs[f'ml_forecasts_{months}m'].copy()
        frame = frame.drop(
            columns=[
                column
                for column in metadata.columns
                if column in frame.columns and column != 'ticker'
            ],
            errors='ignore',
        ).merge(metadata, on='ticker', how='left')
        frame['as_of_date'] = pd.Timestamp(as_of_date)
        frame['forecast_date'] = pd.Timestamp(as_of_date)
        frame['horizon'] = f'{months}M'
        frame['horizon_months'] = months
        frame['evidence_mode'] = evidence_mode
        frame['model_version'] = 'wolf_deterministic_forecast_v1'
        rows.append(frame)
    return pd.concat(rows, ignore_index=True), outputs['ml_features']


def build_realised_outcomes(
    forecasts: pd.DataFrame,
    price_matcher: _PriceMatcher,
    tolerance_days: int,
) -> pd.DataFrame:
    if forecasts.empty:
        return pd.DataFrame()
    requests = forecasts[
        ['security_id', 'ticker', 'as_of_date', 'horizon', 'horizon_months']
    ].copy()
    requests['target_date'] = [
        pd.Timestamp(date) + pd.DateOffset(months=int(months))
        for date, months in zip(requests['as_of_date'], requests['horizon_months'])
    ]
    starts = price_matcher.match_requests(
        requests,
        'as_of_date',
        'backward',
        tolerance_days,
    ).rename(
        columns={
            'matched_trade_date': 'start_trade_date',
            'matched_adjusted_close': 'start_adjusted_close',
            'matched_close_price': 'start_close_price',
        }
    )
    if starts.empty:
        return pd.DataFrame()
    ends = price_matcher.match_requests(
        starts,
        'target_date',
        'forward',
        tolerance_days,
    ).rename(
        columns={
            'matched_trade_date': 'end_trade_date',
            'matched_adjusted_close': 'end_adjusted_close',
            'matched_close_price': 'end_close_price',
        }
    )
    if ends.empty:
        return pd.DataFrame()
    ends['realised_return'] = (
        ends['end_adjusted_close'] / ends['start_adjusted_close'] - 1.0
    )
    ends['outcome_date'] = pd.to_datetime(ends['end_trade_date'])
    return ends[
        [
            'security_id',
            'ticker',
            'as_of_date',
            'horizon',
            'horizon_months',
            'target_date',
            'start_trade_date',
            'end_trade_date',
            'outcome_date',
            'start_adjusted_close',
            'end_adjusted_close',
            'realised_return',
        ]
    ].reset_index(drop=True)


def _cardinality_constrained_portfolio(
    scorecard: pd.DataFrame,
    constraints: dict[str, Any],
) -> pd.DataFrame:
    eligible = scorecard.loc[scorecard['passes_hard_filters'].fillna(False)].copy()
    eligible = eligible.sort_values(
        ['final_recommendation_score', 'ticker'],
        ascending=[False, True],
        kind='stable',
    ).drop_duplicates('issuer_id')
    if eligible.empty:
        raise RuntimeError('No names satisfied the historical portfolio constraints.')
    position_weight = float(constraints.get('max_single_name_weight', 0.05))
    if not 0 < position_weight <= 1:
        raise ValueError('max_single_name_weight must be between zero and one.')

    def group_holding_limit(weight_limit: float) -> int:
        return int(np.floor(weight_limit / position_weight + 1.0e-9))

    group_limits = {
        'sector': group_holding_limit(
            float(constraints.get('max_sector_weight', 0.25))
        ),
        'country': group_holding_limit(
            float(constraints.get('max_country_weight', 0.30))
        ),
        'region': group_holding_limit(
            float(constraints.get('max_region_weight', 0.40))
        ),
        'currency': group_holding_limit(
            float(constraints.get('max_currency_weight', 0.40))
        ),
    }
    constraint_rows = [np.ones(len(eligible), dtype=float)]
    upper_bounds = [20.0]
    for column, limit in group_limits.items():
        labels = eligible[column].fillna('<missing>').astype(str)
        for label in sorted(labels.unique()):
            constraint_rows.append(labels.eq(label).to_numpy(dtype=float))
            upper_bounds.append(float(limit))
    scores = pd.to_numeric(
        eligible['final_recommendation_score'],
        errors='coerce',
    ).fillna(0.0).clip(0.0, 100.0)
    objective = -(1.0 + scores.to_numpy(dtype=float) * 1.0e-5)
    result = milp(
        c=objective,
        integrality=np.ones(len(eligible), dtype=int),
        bounds=Bounds(0.0, 1.0),
        constraints=LinearConstraint(
            np.vstack(constraint_rows),
            np.full(len(constraint_rows), -np.inf),
            np.asarray(upper_bounds, dtype=float),
        ),
        options={'time_limit': 5.0},
    )
    selected = (
        eligible.index[np.asarray(result.x) > 0.5].tolist()
        if result.success and result.x is not None
        else []
    )
    minimum_holdings = int(constraints.get('minimum_effective_number_of_holdings', 15))
    cash_weight = max(1.0 - len(selected) * position_weight, 0.0)
    maximum_cash_weight = float(constraints.get('maximum_cash_weight', 0.25))
    if len(selected) < minimum_holdings or cash_weight > maximum_cash_weight + 1.0e-9:
        raise RuntimeError(
            f'Only {len(selected)} names satisfied the historical portfolio constraints; '
            f'required cash weight would be {cash_weight:.2%}.'
        )
    portfolio = scorecard.loc[selected].copy()
    portfolio['target_weight'] = position_weight
    portfolio['optimisation_feasible'] = True
    portfolio['optimisation_status'] = (
        'cardinality_constraint_cash_fallback'
        if cash_weight > 1.0e-10
        else 'cardinality_constraint_fallback'
    )
    if cash_weight > 1.0e-10:
        cash = {column: pd.NA for column in portfolio.columns}
        cash.update(
            {
                'security_id': CASH_SECURITY_ID,
                'ticker': CASH_SECURITY_ID,
                'issuer_id': CASH_SECURITY_ID,
                'company_name': 'USD Cash',
                'instrument_type': 'Cash',
                'listing_status': 'Active',
                'exchange_code': 'CASH',
                'country': 'Cash',
                'region': 'Cash',
                'sector': 'Cash',
                'industry': 'Cash',
                'currency': 'USD',
                'market_cap_usd': 0.0,
                'average_daily_value_usd': np.inf,
                'volatility_1y': 0.0,
                'passes_hard_filters': True,
                'target_weight': cash_weight,
                'optimisation_feasible': True,
                'optimisation_status': 'cardinality_constraint_cash_fallback',
            }
        )
        portfolio = pd.concat([portfolio, pd.DataFrame([cash])], ignore_index=True)
    return portfolio


def _weights_satisfy_linear_caps(
    weights: pd.Series,
    scorecard: pd.DataFrame,
    constraints: dict[str, Any],
) -> bool:
    if abs(float(weights.sum()) - 1.0) > 1.0e-6 or bool(weights.lt(-1.0e-10).any()):
        return False
    cash_weight = float(weights.get(CASH_SECURITY_ID, 0.0))
    if cash_weight > float(constraints.get('maximum_cash_weight', 0.25)) + 1.0e-8:
        return False
    risky = weights.loc[weights.index.astype(str) != CASH_SECURITY_ID]
    if risky.empty:
        return False
    if risky.max() > float(constraints.get('max_single_name_weight', 0.05)) + 1.0e-8:
        return False
    metadata = scorecard.drop_duplicates('security_id').set_index('security_id')
    if not set(risky.index).issubset(metadata.index):
        return False
    for column, key in (
        ('sector', 'max_sector_weight'),
        ('country', 'max_country_weight'),
        ('region', 'max_region_weight'),
        ('currency', 'max_currency_weight'),
    ):
        exposure = (
            metadata.loc[risky.index, [column]]
            .assign(_weight=risky.to_numpy())
            .groupby(column, dropna=False)['_weight']
            .sum()
        )
        if not exposure.empty and exposure.max() > float(constraints.get(key, 1.0)) + 1.0e-8:
            return False
    return True


def _cash_row(columns: pd.Index, weight: float) -> dict[str, Any]:
    row = {column: pd.NA for column in columns}
    row.update(
        {
            'security_id': CASH_SECURITY_ID,
            'ticker': CASH_SECURITY_ID,
            'issuer_id': CASH_SECURITY_ID,
            'company_name': 'USD Cash',
            'instrument_type': 'Cash',
            'listing_status': 'Active',
            'exchange_code': 'CASH',
            'country': 'Cash',
            'region': 'Cash',
            'sector': 'Cash',
            'industry': 'Cash',
            'currency': 'USD',
            'market_cap_usd': 0.0,
            'average_daily_value_usd': np.inf,
            'volatility_1y': 0.0,
            'passes_hard_filters': True,
            'target_weight': weight,
            'optimisation_feasible': True,
        }
    )
    return row


def _minimum_turnover_hard_exit_portfolio(
    current: pd.Series,
    target: pd.Series,
    forced: pd.Series,
    scorecard: pd.DataFrame,
    constraints: dict[str, Any],
) -> pd.Series | None:
    """Find the closest feasible portfolio after non-negotiable exits."""

    index = current.index
    count = len(index)
    metadata = scorecard.drop_duplicates('security_id').set_index('security_id')
    rows: list[np.ndarray] = []
    bounds: list[float] = []

    # |w - current| <= u linearisation.
    identity = np.eye(count)
    rows.extend(
        np.hstack([identity, -identity])[position]
        for position in range(count)
    )
    bounds.extend(current.to_numpy(dtype=float))
    rows.extend(
        np.hstack([-identity, -identity])[position]
        for position in range(count)
    )
    bounds.extend((-current).to_numpy(dtype=float))

    for column, key in (
        ('sector', 'max_sector_weight'),
        ('country', 'max_country_weight'),
        ('region', 'max_region_weight'),
        ('currency', 'max_currency_weight'),
    ):
        cap = float(constraints.get(key, 1.0))
        if cap >= 1.0:
            continue
        labels = pd.Series('Cash', index=index, dtype=object)
        risky_ids = index[index.astype(str) != CASH_SECURITY_ID]
        if not set(risky_ids).issubset(metadata.index) or column not in metadata:
            return None
        labels.loc[risky_ids] = metadata.loc[risky_ids, column].fillna('Unknown').astype(str)
        for label in labels.loc[risky_ids].unique():
            coefficients = np.zeros(count * 2, dtype=float)
            coefficients[:count] = labels.eq(label).to_numpy(dtype=float)
            rows.append(coefficients)
            bounds.append(cap)

    objective = np.concatenate(
        [
            -1.0e-6 * target.to_numpy(dtype=float),
            np.ones(count, dtype=float),
        ]
    )
    variable_bounds: list[tuple[float, float | None]] = []
    max_single = float(constraints.get('max_single_name_weight', 0.05))
    max_cash = float(constraints.get('maximum_cash_weight', 0.25))
    for security_id, must_exit in zip(index, forced.to_numpy(dtype=bool)):
        if must_exit:
            variable_bounds.append((0.0, 0.0))
        elif str(security_id) == CASH_SECURITY_ID:
            variable_bounds.append((0.0, max_cash))
        else:
            variable_bounds.append((0.0, max_single))
    variable_bounds.extend([(0.0, None)] * count)
    result = linprog(
        c=objective,
        A_ub=np.vstack(rows) if rows else None,
        b_ub=np.asarray(bounds, dtype=float) if bounds else None,
        A_eq=np.concatenate([np.ones(count), np.zeros(count)]).reshape(1, -1),
        b_eq=np.array([1.0]),
        bounds=variable_bounds,
        method='highs',
    )
    if not result.success or result.x is None:
        return None
    weights = pd.Series(result.x[:count], index=index, dtype=float).clip(lower=0.0)
    weights.loc[weights.abs().lt(1.0e-12)] = 0.0
    weights /= weights.sum()
    return weights


def _apply_walk_forward_rebalance_control(
    target_portfolio: pd.DataFrame,
    previous_weights: pd.Series | None,
    scorecard: pd.DataFrame,
    constraints: dict[str, Any],
) -> pd.DataFrame:
    target_portfolio = target_portfolio.copy()
    if previous_weights is None:
        target_portfolio['rebalance_control_applied'] = False
        target_portfolio['forced_exit_turnover'] = 0.0
        target_portfolio['no_trade_band_applied'] = False
        return target_portfolio

    target = pd.Series(
        pd.to_numeric(target_portfolio['target_weight'], errors='coerce').fillna(0.0).to_numpy(),
        index=target_portfolio['security_id'].astype(str),
        dtype=float,
    ).groupby(level=0).sum()
    current = pd.Series(previous_weights, dtype=float).fillna(0.0).clip(lower=0.0)
    if abs(float(target.sum()) - 1.0) > 1.0e-6 or abs(float(current.sum()) - 1.0) > 1.0e-6:
        target_portfolio['rebalance_control_applied'] = False
        target_portfolio['forced_exit_turnover'] = 0.0
        target_portfolio['no_trade_band_applied'] = False
        return target_portfolio

    union = target.index.union(current.index)
    target = target.reindex(union, fill_value=0.0)
    current = current.reindex(union, fill_value=0.0)
    retention_data = scorecard.copy()
    if 'final_recommendation' not in retention_data and 'recommendation' in retention_data:
        retention_data['final_recommendation'] = retention_data['recommendation']
    retention_data['current_weight'] = (
        retention_data['security_id'].astype(str).map(current).fillna(0.0)
    )
    retention = build_retention_eligibility_mask(retention_data, constraints)
    retention_by_id = pd.Series(
        retention.to_numpy(), index=retention_data['security_id'].astype(str)
    ).groupby(level=0).max()
    retention_by_id.loc[CASH_SECURITY_ID] = True
    forced = current.gt(1.0e-12) & ~current.index.to_series().map(
        retention_by_id
    ).fillna(False).to_numpy()

    forced_weight = float(current.loc[forced].sum())
    if forced_weight > 0:
        post_exit = _minimum_turnover_hard_exit_portfolio(
            current,
            target,
            forced,
            retention_data,
            constraints,
        )
    else:
        post_exit = current.copy()
    feasibility_override = post_exit is None
    if post_exit is None:
        post_exit = target.copy()
    forced_exit_turnover = float(0.5 * (post_exit - current).abs().sum())
    desired_turnover = float(0.5 * (target - current).abs().sum())
    remaining_turnover = float(0.5 * (target - post_exit).abs().sum())
    maximum_turnover = float(constraints.get('maximum_turnover', 1.0))
    no_trade_band = float(constraints.get('minimum_rebalance_turnover', 0.0))
    no_trade = forced_weight <= 1.0e-12 and desired_turnover <= no_trade_band
    if no_trade:
        controlled = current.copy()
    elif remaining_turnover > 1.0e-12:
        budget = max(maximum_turnover - forced_exit_turnover, 0.0)
        scale = min(budget / remaining_turnover, 1.0)
        controlled = post_exit + scale * (target - post_exit)
    else:
        controlled = post_exit
    controlled = controlled.clip(lower=0.0)
    controlled /= controlled.sum()

    feasibility_override |= not _weights_satisfy_linear_caps(
        controlled, scorecard, constraints
    )
    if feasibility_override:
        controlled = target

    metadata = target_portfolio.drop_duplicates('security_id').set_index('security_id')
    missing_ids = [
        security_id
        for security_id in controlled.index[controlled.gt(1.0e-10)]
        if security_id not in metadata.index and security_id != CASH_SECURITY_ID
    ]
    if missing_ids:
        additions = scorecard.loc[
            scorecard['security_id'].astype(str).isin(missing_ids)
        ].drop_duplicates('security_id').set_index('security_id')
        metadata = pd.concat([metadata, additions], axis=0, sort=False)
    if controlled.get(CASH_SECURITY_ID, 0.0) > 1.0e-10 and CASH_SECURITY_ID not in metadata.index:
        cash = pd.DataFrame(
            [_cash_row(metadata.columns.append(pd.Index(['security_id'])), 0.0)]
        ).set_index('security_id')
        metadata = pd.concat([metadata, cash], axis=0, sort=False)
    selected = controlled.index[controlled.gt(1.0e-10)]
    output = metadata.loc[selected].copy().reset_index()
    output['target_weight'] = output['security_id'].astype(str).map(controlled)
    output['unconstrained_turnover'] = desired_turnover
    output['projected_turnover'] = float(0.5 * (controlled - current).abs().sum())
    output['turnover_constraint_applied'] = output['projected_turnover'].iloc[0] + 1.0e-12 < desired_turnover
    output['rebalance_control_applied'] = True
    output['forced_exit_turnover'] = forced_exit_turnover
    output['forced_exit_weight'] = forced_weight
    output['no_trade_band_applied'] = no_trade
    output['turnover_control_feasibility_override'] = feasibility_override
    output['optimisation_feasible'] = True
    return output


def _build_anchor_portfolios(
    features: pd.DataFrame,
    forecast_wide: pd.DataFrame,
    previous_wolf_weights: pd.Series | None = None,
    maximum_rebalance_turnover: float = 0.10,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    merge_columns = [
        column
        for column in forecast_wide.columns
        if column == 'ticker' or column not in features.columns
    ]
    model_features = features.merge(
        forecast_wide[merge_columns],
        on='ticker',
        how='left',
    )
    risk_limits = load_yaml('configs/risk_limits.yaml')
    scorecard = build_scorecard(model_features, risk_limits)
    optimisation = load_yaml('configs/optimisation.yaml').get('optimisation', {})
    constraints = dict(optimisation.get('constraints', {}))
    constraints['maximum_candidates'] = int(optimisation.get('maximum_candidates', 2000))
    constraints['maximum_turnover'] = float(maximum_rebalance_turnover)
    optimiser_input = build_optimiser_input_dataset(scorecard)
    if previous_wolf_weights is not None:
        optimiser_input['current_weight'] = (
            optimiser_input['security_id']
            .astype(str)
            .map(previous_wolf_weights)
            .fillna(0.0)
        )
    wolf = cvar_constrained_portfolio(optimiser_input, constraints)
    wolf = wolf.loc[pd.to_numeric(wolf['target_weight'], errors='coerce').gt(1.0e-10)]
    feasible = (
        not wolf.empty
        and bool(wolf.get('optimisation_feasible', pd.Series(False)).fillna(False).all())
        and abs(float(wolf['target_weight'].sum()) - 1.0) <= 1.0e-6
    )
    if not feasible:
        wolf = _cardinality_constrained_portfolio(scorecard, constraints)
    wolf = _apply_walk_forward_rebalance_control(
        wolf,
        previous_wolf_weights,
        scorecard,
        constraints,
    )
    wolf = wolf.copy()
    wolf['strategy'] = 'wolf_cvar'
    wolf['weight'] = pd.to_numeric(wolf['target_weight'], errors='coerce')

    benchmark_base = scorecard.loc[
        scorecard['passes_hard_filters'].fillna(False)
    ].sort_values(
        ['final_recommendation_score', 'ticker'],
        ascending=[False, True],
        kind='stable',
    ).drop_duplicates('issuer_id')
    if benchmark_base.empty:
        raise RuntimeError('No eligible historical benchmark securities were available.')
    equal = benchmark_base.copy()
    equal['weight'] = 1.0 / len(equal)
    equal['strategy'] = 'equal_weight_eligible'
    cap_weight = pd.to_numeric(
        benchmark_base['market_cap_usd'],
        errors='coerce',
    ).clip(lower=0)
    cap = benchmark_base.copy()
    cap['weight'] = cap_weight / cap_weight.sum()
    cap['strategy'] = 'cap_weight_eligible'
    return {
        'wolf_cvar': wolf,
        'equal_weight_eligible': equal,
        'cap_weight_eligible': cap,
    }, scorecard


def _series_weights(portfolio: pd.DataFrame) -> pd.Series:
    return pd.Series(
        pd.to_numeric(portfolio['weight'], errors='coerce').to_numpy(),
        index=portfolio['security_id'].astype(str),
        dtype=float,
    )


def _cash_mask(portfolio: pd.DataFrame) -> pd.Series:
    instrument_type = portfolio.get(
        'instrument_type',
        pd.Series('', index=portfolio.index),
    ).astype(str)
    security_id = portfolio['security_id'].astype(str)
    return instrument_type.str.casefold().eq('cash') | security_id.eq(CASH_SECURITY_ID)


def _portfolio_outcome(
    portfolio: pd.DataFrame,
    as_of_date: pd.Timestamp,
    price_matcher: _PriceMatcher,
    tolerance_days: int,
) -> tuple[float, float]:
    cash = _cash_mask(portfolio)
    cash_weight = float(
        pd.to_numeric(portfolio.loc[cash, 'weight'], errors='coerce')
        .fillna(0.0)
        .sum()
    )
    requests = portfolio.loc[~cash, ['security_id', 'ticker']].copy()
    if requests.empty:
        return 0.0, cash_weight
    requests['as_of_date'] = as_of_date
    requests['horizon'] = '1M'
    requests['horizon_months'] = 1
    outcomes = build_realised_outcomes(requests, price_matcher, tolerance_days)
    if outcomes.empty:
        return float('nan'), 0.0
    weights = _series_weights(portfolio)
    outcomes['weight'] = outcomes['security_id'].astype(str).map(weights)
    valid_weight = float(outcomes['weight'].sum()) + cash_weight
    if valid_weight < 0.95:
        return float('nan'), valid_weight
    realised = float(
        (
            outcomes['realised_return']
            * outcomes['weight']
            / valid_weight
        ).sum()
    )
    return realised, valid_weight


def _portfolio_cost(
    current: pd.DataFrame,
    previous_weights: pd.Series | None,
    feature_lookup: pd.DataFrame,
    nav_usd: float,
) -> tuple[float, float]:
    target = _series_weights(current)
    if previous_weights is None:
        delta = target
        turnover = 1.0
    else:
        union = target.index.union(previous_weights.index)
        delta = target.reindex(union, fill_value=0.0) - previous_weights.reindex(
            union,
            fill_value=0.0,
        )
        turnover = float(0.5 * delta.abs().sum())
    costs = load_yaml('configs/validation.yaml').get('validation', {}).get('costs', {})
    lookup = feature_lookup.set_index('security_id', drop=False)
    total_cost = 0.0
    for security_id, weight_change in delta.items():
        if abs(float(weight_change)) <= 1.0e-12:
            continue
        if str(security_id) == CASH_SECURITY_ID:
            continue
        row = lookup.loc[security_id] if security_id in lookup.index else pd.Series()
        estimate = estimate_transaction_cost(
            traded_notional=abs(float(weight_change)) * nav_usd,
            commission_bps=float(costs.get('base_commission_bps', 5.0)),
            half_spread_bps=float(costs.get('half_spread_bps', 7.5)),
            slippage_bps=float(costs.get('slippage_bps', 5.0)),
            volatility=float(row.get('volatility_1y', 0.25)),
            average_daily_value=float(row.get('average_daily_value_usd', np.nan)),
            impact_coefficient=float(costs.get('impact_coefficient', 0.10)),
        )
        total_cost += float(estimate['total_cost'])
    return turnover, total_cost / nav_usd


def _weighted_daily_returns(
    prices: pd.DataFrame,
    weights: pd.Series,
    minimum_coverage: float = 0.80,
) -> pd.Series:
    if prices.empty:
        return pd.Series(dtype=float)
    matrix = prices.pivot_table(
        index='trade_date',
        columns='security_id',
        values='return',
        aggfunc='last',
    )
    aligned_weights = weights.reindex(matrix.columns.astype(str), fill_value=0.0)
    aligned_weights.index = matrix.columns
    cash_weight = float(
        weights.loc[weights.index.astype(str) == CASH_SECURITY_ID].sum()
    )
    coverage = (
        matrix.notna().mul(aligned_weights, axis=1).sum(axis=1) + cash_weight
    )
    weighted = matrix.fillna(0.0).mul(aligned_weights, axis=1).sum(axis=1)
    return (weighted / coverage.replace(0, np.nan)).loc[coverage.ge(minimum_coverage)].dropna()


def _asset_return_matrix(
    prices: pd.DataFrame,
    weights: pd.Series,
    minimum_coverage: float = 0.80,
) -> pd.DataFrame:
    risky_weights = weights.loc[
        weights.index.astype(str) != CASH_SECURITY_ID
    ].astype(float)
    if prices.empty or risky_weights.empty:
        return pd.DataFrame()
    matrix = prices.pivot_table(
        index='trade_date',
        columns='security_id',
        values='return',
        aggfunc='last',
    ).reindex(columns=risky_weights.index)
    cash_weight = float(weights.get(CASH_SECURITY_ID, 0.0))
    coverage = matrix.notna().mul(risky_weights, axis=1).sum(axis=1) + cash_weight
    return matrix.loc[coverage.ge(minimum_coverage)].fillna(0.0).sort_index()


def _risk_rows(
    portfolio: pd.DataFrame,
    as_of_date: pd.Timestamp,
    price_matcher: _PriceMatcher,
    config: WalkForwardConfig,
    initial_exception_days: int = 0,
) -> pd.DataFrame:
    weights = _series_weights(portfolio)
    security_ids = weights.index.astype(str).tolist()
    trailing, _ = price_matcher.trailing(
        security_ids,
        as_of_date,
        config.risk_lookback_rows + 1,
    )
    historical = _weighted_daily_returns(trailing, weights).tail(
        config.risk_lookback_rows
    )
    historical_assets = _asset_return_matrix(trailing, weights).tail(
        config.risk_lookback_rows
    )
    target_date = as_of_date + pd.DateOffset(months=1)
    realised_prices = price_matcher.between(security_ids, as_of_date, target_date)
    realised = _weighted_daily_returns(realised_prices, weights).sort_index()
    realised_assets = _asset_return_matrix(realised_prices, weights)
    settings = _risk_model_settings(config)
    if len(historical) < settings.minimum_training_rows or realised.empty:
        return pd.DataFrame()
    history = historical.astype(float).copy()
    asset_history = historical_assets.copy()
    risky_weights = weights.loc[
        weights.index.astype(str) != CASH_SECURITY_ID
    ].astype(float)
    (
        selected_model,
        selected_scale_factor,
        candidate_scores,
        calibration_rows,
    ) = select_risk_model(
        history,
        settings,
        asset_returns=asset_history,
        asset_weights=risky_weights,
    )
    rows: list[dict[str, Any]] = []
    exception_days_remaining = max(int(initial_exception_days), 0)
    for date, realised_return in realised.items():
        sample = history.tail(config.risk_lookback_rows)
        forecast = forecast_risk(
            sample,
            selected_model,
            settings,
            asset_returns=asset_history.tail(config.risk_lookback_rows),
            asset_weights=risky_weights,
        )
        exception_response_active = exception_days_remaining > 0
        effective_scale_factor = selected_scale_factor * (
            config.risk_exception_response_multiplier
            if exception_response_active
            else 1.0
        )
        calibrated_values = {
            name: value * effective_scale_factor
            for name, value in forecast.values.items()
        }
        exception_days_before = exception_days_remaining
        exception_days_remaining = max(exception_days_remaining - 1, 0)
        exception_triggered = float(realised_return) < calibrated_values['var_95']
        if exception_triggered:
            exception_days_remaining = max(
                exception_days_remaining,
                config.risk_exception_response_days,
            )
        rows.append(
            {
                'date': pd.Timestamp(date),
                'as_of_date': as_of_date,
                'strategy': 'wolf_cvar',
                'realised_return': float(realised_return),
                **calibrated_values,
                'raw_forecast_volatility': forecast.volatility,
                'forecast_volatility': forecast.volatility * effective_scale_factor,
                'risk_model': f'daily_{forecast.model}',
                'risk_calibration_scale_factor': selected_scale_factor,
                'risk_effective_scale_factor': effective_scale_factor,
                'risk_exception_response_active': exception_response_active,
                'risk_exception_triggered': exception_triggered,
                'risk_exception_days_before': exception_days_before,
                'risk_exception_days_after': exception_days_remaining,
                'risk_model_selection_scores': serialise_scores(candidate_scores),
                'risk_model_calibration_observations': calibration_rows,
                'ewma_decay': config.risk_ewma_decay,
                'training_observations': len(sample),
                'training_end_date': pd.Timestamp(history.index.max()),
                'evidence_mode': config.evidence_mode,
            }
        )
        history.loc[pd.Timestamp(date)] = float(realised_return)
        if date in realised_assets.index:
            asset_history.loc[pd.Timestamp(date)] = realised_assets.loc[date]
    result = pd.DataFrame(rows)
    result.attrs['exception_days_remaining'] = exception_days_remaining
    return result


def _constraint_rows(
    portfolio: pd.DataFrame,
    as_of_date: pd.Timestamp,
) -> pd.DataFrame:
    optimisation = load_yaml('configs/optimisation.yaml').get('optimisation', {})
    limits = optimisation.get('constraints', {})
    weights = _series_weights(portfolio)
    risky_portfolio = portfolio.loc[~_cash_mask(portfolio)].copy()
    risky_weights = _series_weights(risky_portfolio)
    cash_weight = float(weights.get(CASH_SECURITY_ID, 0.0))
    rows = [
        {
            'as_of_date': as_of_date,
            'strategy': 'wolf_cvar',
            'constraint_name': 'weights_sum_to_one',
            'constraint_type': 'hard',
            'actual_value': float(weights.sum()),
            'limit_value': 1.0,
            'breach_flag': abs(float(weights.sum()) - 1.0) > 1.0e-6,
        },
        {
            'as_of_date': as_of_date,
            'strategy': 'wolf_cvar',
            'constraint_name': 'maximum_single_name_weight',
            'constraint_type': 'hard',
            'actual_value': float(risky_weights.max()) if not risky_weights.empty else 0.0,
            'limit_value': float(limits.get('max_single_name_weight', 0.05)),
            'breach_flag': (float(risky_weights.max()) if not risky_weights.empty else 0.0)
            > float(limits.get('max_single_name_weight', 0.05)) + 1.0e-6,
        },
        {
            'as_of_date': as_of_date,
            'strategy': 'wolf_cvar',
            'constraint_name': 'maximum_cash_weight',
            'constraint_type': 'hard',
            'actual_value': cash_weight,
            'limit_value': float(limits.get('maximum_cash_weight', 0.25)),
            'breach_flag': cash_weight
            > float(limits.get('maximum_cash_weight', 0.25)) + 1.0e-6,
        },
    ]
    group_limits = {
        'sector': 'max_sector_weight',
        'country': 'max_country_weight',
        'region': 'max_region_weight',
        'currency': 'max_currency_weight',
    }
    for column, key in group_limits.items():
        exposure = (
            risky_portfolio.assign(_weight=risky_portfolio['weight'])
            .groupby(column, dropna=False)['_weight']
            .sum()
        )
        actual = float(exposure.max()) if not exposure.empty else 0.0
        limit = float(limits.get(key, 1.0))
        rows.append(
            {
                'as_of_date': as_of_date,
                'strategy': 'wolf_cvar',
                'constraint_name': f'maximum_{column}_weight',
                'constraint_type': 'hard',
                'actual_value': actual,
                'limit_value': limit,
                'breach_flag': actual > limit + 1.0e-6,
            }
        )
    return pd.DataFrame(rows)


def _atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    frame.to_parquet(temporary, index=False, compression='zstd')
    temporary.replace(path)


def _atomic_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str),
        encoding='utf-8',
    )
    temporary.replace(path)


def _frame_hash(frame: pd.DataFrame, columns: list[str]) -> str:
    digest = hashlib.sha256()
    if frame.empty:
        return digest.hexdigest()
    values = frame[columns].astype(str).sort_values(columns).agg('|'.join, axis=1)
    for value in values:
        digest.update(value.encode('utf-8'))
    return digest.hexdigest()


def run_walk_forward(config: WalkForwardConfig | None = None) -> WalkForwardResult:
    config = config or load_walk_forward_config()
    if config.start_date > config.forecast_end_date:
        raise ValueError('Walk-forward start date must not exceed forecast end date.')
    if config.forecast_end_date > config.strategy_end_date:
        raise ValueError('Forecast end date must not exceed strategy end date.')
    data_config = load_data_config()
    repository = DuckDBRepository(data_config.duckdb_path, read_only=True)
    LOGGER.info('Loading observed walk-forward source data from %s.', data_config.duckdb_path)
    universe, statements_raw, prices_raw, fx, market_caps = _load_source_data(
        repository,
        config,
    )
    if universe.empty or statements_raw.empty or prices_raw.empty:
        raise RuntimeError('Observed walk-forward source data is incomplete.')
    fx_matcher = _FxMatcher(fx)
    prices = _prepare_prices(prices_raw)
    statements = _prepare_statements(
        statements_raw,
        universe,
        fx_matcher,
        config.filing_lag_days,
    )
    price_matcher = _PriceMatcher(prices)
    market_cap_matcher = _MarketCapMatcher(market_caps)
    anchors = pd.date_range(
        config.start_date,
        config.strategy_end_date,
        freq='ME',
    )

    forecast_frames: list[pd.DataFrame] = []
    outcome_frames: list[pd.DataFrame] = []
    weight_frames: list[pd.DataFrame] = []
    portfolio_rows: list[dict[str, Any]] = []
    risk_frames: list[pd.DataFrame] = []
    constraint_frames: list[pd.DataFrame] = []
    anchor_rows: list[dict[str, Any]] = []
    previous_weights: dict[str, pd.Series] = {}
    risk_exception_days = 0

    for position, anchor in enumerate(anchors, start=1):
        features, recent = _build_anchor_inputs(
            universe,
            statements,
            price_matcher,
            fx_matcher,
            market_cap_matcher,
            pd.Timestamp(anchor),
            config,
        )
        if features.empty:
            raise RuntimeError(f'No point-in-time features were available at {anchor.date()}.')
        forecasts, forecast_wide = _forecast_anchor(
            features,
            pd.Timestamp(anchor),
            config.evidence_mode,
        )
        if anchor <= config.forecast_end_date:
            realised = build_realised_outcomes(
                forecasts,
                price_matcher,
                config.outcome_date_tolerance_days,
            )
            forecast_frames.append(forecasts)
            outcome_frames.append(realised)

        portfolios, scorecard = _build_anchor_portfolios(
            features,
            forecast_wide,
            previous_weights.get(config.primary_strategy),
            config.maximum_rebalance_turnover,
        )
        regime = (
            'high_volatility'
            if float(features['volatility_1y'].median()) > 0.30
            else 'negative_momentum'
            if float(features['momentum_6m'].median()) < 0
            else 'steady'
        )
        for strategy, portfolio in portfolios.items():
            portfolio = portfolio.copy()
            gross_return, valid_weight = _portfolio_outcome(
                portfolio,
                pd.Timestamp(anchor),
                price_matcher,
                config.outcome_date_tolerance_days,
            )
            turnover, transaction_cost = _portfolio_cost(
                portfolio,
                previous_weights.get(strategy),
                scorecard,
                config.portfolio_nav_usd,
            )
            previous_weights[strategy] = _series_weights(portfolio)
            portfolio['as_of_date'] = pd.Timestamp(anchor)
            portfolio['evidence_mode'] = config.evidence_mode
            portfolio['strategy'] = strategy
            weight_frames.append(portfolio)
            portfolio_rows.append(
                {
                    'date': pd.Timestamp(anchor) + pd.DateOffset(months=1),
                    'as_of_date': pd.Timestamp(anchor),
                    'strategy': strategy,
                    'gross_return': gross_return,
                    'transaction_cost': transaction_cost,
                    'net_return': gross_return - transaction_cost,
                    'turnover': turnover,
                    'valid_outcome_weight': valid_weight,
                    'holding_count': int(
                        (
                            portfolio['weight'].gt(1.0e-10)
                            & ~_cash_mask(portfolio)
                        ).sum()
                    ),
                    'cash_weight': float(
                        pd.to_numeric(
                            portfolio.loc[_cash_mask(portfolio), 'weight'],
                            errors='coerce',
                        ).fillna(0.0).sum()
                    ),
                    'regime': regime,
                    'evidence_mode': config.evidence_mode,
                }
            )

        wolf = portfolios['wolf_cvar']
        risk = _risk_rows(
            wolf,
            pd.Timestamp(anchor),
            price_matcher,
            config,
            initial_exception_days=risk_exception_days,
        )
        if not risk.empty:
            risk_exception_days = int(
                risk.attrs.get('exception_days_remaining', 0)
            )
            risk_frames.append(risk)
        constraint_frames.append(_constraint_rows(wolf, pd.Timestamp(anchor)))
        region_counts = (
            features.groupby('region')['security_id']
            .nunique()
            .sort_index()
            .astype(int)
            .to_dict()
        )
        source_counts = (
            features.groupby('fundamentals_data_source')['security_id']
            .nunique()
            .sort_index()
            .astype(int)
            .to_dict()
        )
        anchor_rows.append(
            {
                'as_of_date': pd.Timestamp(anchor),
                'feature_security_count': len(features),
                'feature_region_count': len(region_counts),
                'feature_regions': ', '.join(region_counts),
                'feature_region_counts': json.dumps(region_counts, sort_keys=True),
                'feature_source_count': len(source_counts),
                'feature_source_counts': json.dumps(source_counts, sort_keys=True),
                'forecast_security_count': forecasts['security_id'].nunique(),
                'wolf_holding_count': int(
                    (wolf['weight'].gt(1.0e-10) & ~_cash_mask(wolf)).sum()
                ),
                'wolf_cash_weight': float(
                    pd.to_numeric(
                        wolf.loc[_cash_mask(wolf), 'weight'],
                        errors='coerce',
                    ).fillna(0.0).sum()
                ),
                'latest_price_feature_date': pd.to_datetime(
                    features['price_feature_end_date']
                ).max(),
                'latest_fundamental_available_from': pd.to_datetime(
                    features['fundamentals_available_from']
                ).max(),
            }
        )
        LOGGER.info(
            'Walk-forward anchor %s/%s %s: features=%s holdings=%s.',
            position,
            len(anchors),
            anchor.date(),
            len(features),
            int((wolf['weight'].gt(1.0e-10) & ~_cash_mask(wolf)).sum()),
        )

    historical_forecasts = pd.concat(forecast_frames, ignore_index=True)
    outcomes = pd.concat(outcome_frames, ignore_index=True)
    portfolio_weights = pd.concat(weight_frames, ignore_index=True, sort=False)
    portfolio_returns = pd.DataFrame(portfolio_rows)
    risk_forecasts = pd.concat(risk_frames, ignore_index=True)
    constraints = pd.concat(constraint_frames, ignore_index=True)
    anchor_summary = pd.DataFrame(anchor_rows)

    chronology_checks = {
        'future_fundamental_rows': int(
            (
                pd.to_datetime(historical_forecasts['fundamentals_available_from'])
                > pd.to_datetime(historical_forecasts['as_of_date'])
            ).sum()
        ),
        'future_price_feature_rows': int(
            (
                pd.to_datetime(historical_forecasts['price_feature_end_date'])
                > pd.to_datetime(historical_forecasts['as_of_date'])
            ).sum()
        ),
        'outcomes_before_target_rows': int(
            (
                pd.to_datetime(outcomes['end_trade_date'])
                < pd.to_datetime(outcomes['target_date'])
            ).sum()
        ),
        'hard_constraint_breaches': int(constraints['breach_flag'].fillna(False).sum()),
    }
    if any(chronology_checks.values()):
        raise RuntimeError(f'Walk-forward chronology checks failed: {chronology_checks}')

    output = config.output_directory
    _atomic_parquet(historical_forecasts, output / 'historical_forecasts.parquet')
    _atomic_parquet(outcomes, output / 'historical_realised_outcomes.parquet')
    _atomic_parquet(portfolio_weights, output / 'historical_portfolio_weights.parquet')
    _atomic_parquet(portfolio_returns, output / 'historical_portfolio_returns.parquet')
    _atomic_parquet(risk_forecasts, output / 'historical_risk_forecasts.parquet')
    _atomic_parquet(constraints, output / 'historical_constraint_report.parquet')
    _atomic_parquet(anchor_summary, output / 'walk_forward_anchor_summary.parquet')

    primary_returns = portfolio_returns.loc[
        portfolio_returns['strategy'].eq(config.primary_strategy)
    ]
    statement_source_counts = (
        statements.groupby('source').size().sort_index().astype(int).to_dict()
    )
    statement_region_counts = (
        statements.merge(
            universe[['security_id', 'region']],
            on='security_id',
            how='left',
        )
        .groupby(['region', 'source'])['security_id']
        .nunique()
        .sort_index()
    )
    manifest = {
        'artifact_version': ARTIFACT_VERSION,
        'generated_at': datetime.now(UTC).isoformat(),
        'evidence_mode': config.evidence_mode,
        'release_approval_cap': config.approval_cap,
        'primary_strategy': config.primary_strategy,
        'configuration': asdict(config),
        'source_database': str(data_config.duckdb_path),
        'source_universe_hash': _frame_hash(universe, ['security_id', 'region']),
        'source_profile': {
            'security_count': int(universe['security_id'].nunique()),
            'statement_rows': len(statements),
            'price_rows': len(prices),
            'price_min_date': pd.to_datetime(prices['trade_date']).min(),
            'price_max_date': pd.to_datetime(prices['trade_date']).max(),
            'fundamental_min_period': pd.to_datetime(
                statements['fiscal_period_end']
            ).min(),
            'fundamental_max_period': pd.to_datetime(
                statements['fiscal_period_end']
            ).max(),
            'statement_rows_by_source': {
                str(source): int(count)
                for source, count in statement_source_counts.items()
            },
            'statement_securities_by_region_and_source': {
                f'{region}|{source}': int(count)
                for (region, source), count in statement_region_counts.items()
            },
        },
        'artifact_profile': {
            'anchors': len(anchors),
            'forecast_rows': len(historical_forecasts),
            'outcome_rows': len(outcomes),
            'aligned_outcome_fraction': len(outcomes) / max(len(historical_forecasts), 1),
            'portfolio_months': int(primary_returns['date'].nunique()),
            'portfolio_weight_rows': len(portfolio_weights),
            'risk_observations': len(risk_forecasts),
            'constraint_rows': len(constraints),
            'first_anchor_security_count': int(
                anchor_summary.iloc[0]['feature_security_count']
            ),
            'first_anchor_region_count': int(
                anchor_summary.iloc[0]['feature_region_count']
            ),
            'last_anchor_security_count': int(
                anchor_summary.iloc[-1]['feature_security_count']
            ),
            'last_anchor_region_count': int(
                anchor_summary.iloc[-1]['feature_region_count']
            ),
        },
        'chronology_checks': chronology_checks,
        'limitations': [
            'Historical filing availability is reconstructed from fiscal period end plus a conservative reporting lag when an observed filing date is unavailable.',
            'Early anchors include only regions and securities for which usable historical filings were available; region counts are reported for every anchor.',
            'When represented countries cannot support full equity investment under hard concentration caps, the reconstruction holds up to 25% in zero-return cash rather than relaxing those caps.',
            'The current active universe and current sector metadata introduce survivorship and reference-data bias.',
            'Historical sentiment, narrative, and regime vintages are unavailable and are held neutral in this reconstruction.',
            'Stored candidate price bars have zero volume, so observed current 3-month ADV is used as a static liquidity proxy.',
            'Adjusted-close outcomes may include provider-side retrospective corporate-action adjustments.',
            'This evidence can support conditional model use but cannot support full production approval.',
        ],
    }
    _atomic_json(manifest, output / 'walk_forward_manifest.json')
    result = WalkForwardResult(
        output_directory=output,
        forecast_rows=len(historical_forecasts),
        outcome_rows=len(outcomes),
        portfolio_months=int(primary_returns['date'].nunique()),
        risk_observations=len(risk_forecasts),
        security_count=int(universe['security_id'].nunique()),
        evidence_mode=config.evidence_mode,
    )
    LOGGER.info(
        'Walk-forward artifacts completed: forecasts=%s outcomes=%s months=%s risk=%s.',
        result.forecast_rows,
        result.outcome_rows,
        result.portfolio_months,
        result.risk_observations,
    )
    return result
